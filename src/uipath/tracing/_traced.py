import importlib
import inspect
import json
import logging
from contextvars import ContextVar
from functools import wraps
from typing import Any, Callable, List, Optional, Tuple

from opentelemetry import context, trace
from opentelemetry.trace import NonRecordingSpan, set_span_in_context

from ._utils import _SpanUtils

logger = logging.getLogger(__name__)

_tracer_instance: Optional[trace.Tracer] = None
# ContextVar to track the currently active span for nesting
_active_traced_span: ContextVar[Optional[trace.Span]] = ContextVar(
    "_active_traced_span", default=None
)


def get_tracer() -> trace.Tracer:
    """Lazily initializes and returns the tracer instance."""
    global _tracer_instance
    if _tracer_instance is None:
        _tracer_instance = trace.get_tracer(__name__)
    return _tracer_instance


class TracingManager:
    """Static utility class to manage tracing implementations and decorated functions."""

    # Registry to track original functions, decorated functions, and their parameters
    # Each entry is (original_func, decorated_func, params)
    _traced_registry: List[Tuple[Callable[..., Any], Callable[..., Any], Any]] = []

    # Custom tracer implementation
    _custom_tracer_implementation = None  # Custom span provider function
    _current_span_provider: Optional[Callable[[], Any]] = None

    @classmethod
    def get_custom_tracer_implementation(cls):
        """Get the currently set custom tracer implementation."""
        return cls._custom_tracer_implementation

    @classmethod
    def register_current_span_provider(
        cls, current_span_provider: Optional[Callable[[], Any]]
    ):
        """Register a custom current span provider function.

        Args:
            current_span_provider: A function that returns the current span from an external
                                 tracing framework. If None, no custom span parenting will be used.
        """
        cls._current_span_provider = current_span_provider

    @staticmethod
    def get_parent_context():
        # Always use the currently active OTel span if valid (recursion / children)
        current_span = trace.get_current_span()
        if current_span is not None and current_span.get_span_context().is_valid:
            return set_span_in_context(current_span)

        # Only for the very top-level call, fallback to LangGraph span
        if TracingManager._current_span_provider is not None:
            try:
                external_span = TracingManager._current_span_provider()
                if external_span is not None:
                    return set_span_in_context(external_span)
            except Exception as e:
                logger.warning(f"Error getting current span from provider: {e}")

        # Last fallback
        return context.get_current()

    @classmethod
    def register_traced_function(cls, original_func, decorated_func, params):
        """Register a function decorated with @traced and its parameters.

        Args:
            original_func: The original function before decoration
            decorated_func: The function after decoration
            params: The parameters used for tracing
        """
        cls._traced_registry.append((original_func, decorated_func, params))

    @classmethod
    def reapply_traced_decorator(cls, tracer_implementation):
        """Reapply a different tracer implementation to all functions previously decorated with @traced.

        Args:
            tracer_implementation: A function that takes the same parameters as _opentelemetry_traced
                                 and returns a decorator. If None, reverts to default implementation.
        """
        tracer_implementation = tracer_implementation or _opentelemetry_traced
        cls._custom_tracer_implementation = tracer_implementation

        # Work with a copy of the registry to avoid modifying it during iteration
        registry_copy = cls._traced_registry.copy()

        for original_func, decorated_func, params in registry_copy:
            # Apply the new decorator with the same parameters
            supported_params = _get_supported_params(tracer_implementation, params)
            new_decorated_func = tracer_implementation(**supported_params)(
                original_func
            )

            logger.debug(
                f"Reapplying decorator to {original_func.__name__}, from {decorated_func.__name__}"
            )

            # If this is a method on a class, we need to update the class
            if hasattr(original_func, "__self__") and hasattr(
                original_func, "__func__"
            ):
                setattr(
                    original_func.__self__.__class__,
                    original_func.__name__,
                    new_decorated_func.__get__(
                        original_func.__self__, original_func.__self__.__class__
                    ),
                )
            else:
                # Replace the function in its module
                if hasattr(original_func, "__module__") and hasattr(
                    original_func, "__qualname__"
                ):
                    try:
                        module = importlib.import_module(original_func.__module__)
                        parts = original_func.__qualname__.split(".")

                        # Handle nested objects
                        obj = module
                        for part in parts[:-1]:
                            obj = getattr(obj, part)

                        setattr(obj, parts[-1], new_decorated_func)

                        # Update the registry entry for this function
                        # Find the index and replace with updated entry
                        for i, (orig, _dec, _p) in enumerate(cls._traced_registry):
                            if orig is original_func:
                                cls._traced_registry[i] = (
                                    original_func,
                                    new_decorated_func,
                                    params,
                                )
                                break
                    except (ImportError, AttributeError) as e:
                        # Log the error but continue processing other functions
                        logger.warning(f"Error reapplying decorator: {e}")
                        continue


def _default_input_processor(inputs):
    """Default input processor that doesn't log any actual input data."""
    return {"redacted": "Input data not logged for privacy/security"}


def _default_output_processor(outputs):
    """Default output processor that doesn't log any actual output data."""
    return {"redacted": "Output data not logged for privacy/security"}


def wait_for_tracers():
    """Wait for all tracers to finish."""
    trace.get_tracer_provider().shutdown()  # type: ignore


def _opentelemetry_traced(
    name: Optional[str] = None,
    run_type: Optional[str] = None,
    span_type: Optional[str] = None,
    input_processor: Optional[Callable[..., Any]] = None,
    output_processor: Optional[Callable[..., Any]] = None,
    recording: bool = True,
):
    """Default tracer implementation using OpenTelemetry.

    Args:
        name: Optional name for the span
        run_type: Optional string to categorize the run type
        span_type: Optional string to categorize the span type. If set to "tool" or "TOOL",
                   the function is treated as an OpenInference tool call with:
                   - openinference.span.kind = "TOOL"
                   - tool.name = function name
                   - span_type = "TOOL"
                   - input.value and output.value (already set by default)
        input_processor: Optional function to process inputs before recording
        output_processor: Optional function to process outputs before recording
        recording: If False, span is not recorded
    """

    def decorator(func):
        trace_name = name or func.__name__

        def get_parent_context():
            """Return a context object for starting the new span."""
            current_span = _active_traced_span.get()
            if current_span is not None and (
                current_span.get_span_context().is_valid
                or isinstance(current_span, NonRecordingSpan)
            ):
                return set_span_in_context(current_span)

            if TracingManager._current_span_provider is not None:
                try:
                    external_span = TracingManager._current_span_provider()
                    if external_span is not None:
                        return set_span_in_context(external_span)
                except Exception as e:
                    logger.warning(f"Error getting current span from provider: {e}")

            return context.get_current()

        def get_span():
            if recording and not isinstance(
                _active_traced_span.get(), NonRecordingSpan
            ):
                ctx = get_parent_context()
                span_cm = get_tracer().start_as_current_span(trace_name, context=ctx)
                span = span_cm.__enter__()
            else:
                span_cm = None
                span = NonRecordingSpan(trace.INVALID_SPAN_CONTEXT)
            return span_cm, span

        # --------- Sync wrapper ---------
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            span_cm, span = get_span()
            token = _active_traced_span.set(span)
            try:
                # Check if this should be treated as a tool call
                is_tool = span_type and span_type.upper() == "TOOL"

                if is_tool:
                    # Set OpenInference tool call attributes
                    span.set_attribute("openinference.span.kind", "TOOL")
                    span.set_attribute("tool.name", trace_name)
                    span.set_attribute("span_type", "TOOL")
                else:
                    span.set_attribute("span_type", span_type or "function_call_sync")

                if run_type is not None:
                    span.set_attribute("run_type", run_type)

                inputs = _SpanUtils.format_args_for_trace_json(
                    inspect.signature(func), *args, **kwargs
                )
                if input_processor:
                    processed_inputs = input_processor(json.loads(inputs))
                    inputs = json.dumps(processed_inputs, default=str)

                # kept for backwards compatibility
                span.set_attribute("inputs", inputs)
                span.set_attribute("input.mime_type", "application/json")
                span.set_attribute("input.value", inputs)

                result = func(*args, **kwargs)
                output = output_processor(result) if output_processor else result
                # kept for backwards compatibility
                span.set_attribute(
                    "output", _SpanUtils.format_object_for_trace_json(output)
                )

                span.set_attribute(
                    "output.value", _SpanUtils.format_object_for_trace_json(output)
                )
                span.set_attribute("output.mime_type", "application/json")
                return result
            except Exception as e:
                span.record_exception(e)
                span.set_status(
                    trace.status.Status(trace.status.StatusCode.ERROR, str(e))
                )
                raise
            finally:
                _active_traced_span.reset(token)
                if span_cm:
                    span_cm.__exit__(None, None, None)

        # --------- Async wrapper ---------
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            span_cm, span = get_span()
            token = _active_traced_span.set(span)
            try:
                # Check if this should be treated as a tool call
                is_tool = span_type and span_type.upper() == "TOOL"

                if is_tool:
                    # Set OpenInference tool call attributes
                    span.set_attribute("openinference.span.kind", "TOOL")
                    span.set_attribute("tool.name", trace_name)
                    span.set_attribute("span_type", "TOOL")
                else:
                    span.set_attribute("span_type", span_type or "function_call_async")

                if run_type is not None:
                    span.set_attribute("run_type", run_type)

                inputs = _SpanUtils.format_args_for_trace_json(
                    inspect.signature(func), *args, **kwargs
                )
                if input_processor:
                    processed_inputs = input_processor(json.loads(inputs))
                    inputs = json.dumps(processed_inputs, default=str)

                # kept for backwards compatibility
                span.set_attribute("inputs", inputs)

                span.set_attribute("input.mime_type", "application/json")
                span.set_attribute("input.value", inputs)

                result = await func(*args, **kwargs)
                output = output_processor(result) if output_processor else result
                # kept for backwards compatibility
                span.set_attribute(
                    "output", _SpanUtils.format_object_for_trace_json(output)
                )
                span.set_attribute(
                    "output.value", _SpanUtils.format_object_for_trace_json(output)
                )
                span.set_attribute("output.mime_type", "application/json")
                return result
            except Exception as e:
                span.record_exception(e)
                span.set_status(
                    trace.status.Status(trace.status.StatusCode.ERROR, str(e))
                )
                raise
            finally:
                _active_traced_span.reset(token)
                if span_cm:
                    span_cm.__exit__(None, None, None)

        # --------- Generator wrapper ---------
        @wraps(func)
        def generator_wrapper(*args, **kwargs):
            span_cm, span = get_span()
            token = _active_traced_span.set(span)
            try:
                # Check if this should be treated as a tool call
                is_tool = span_type and span_type.upper() == "TOOL"

                if is_tool:
                    # Set OpenInference tool call attributes
                    span.set_attribute("openinference.span.kind", "TOOL")
                    span.set_attribute("tool.name", trace_name)
                    span.set_attribute("span_type", "TOOL")
                else:
                    span.set_attribute(
                        "span_type", span_type or "function_call_generator_sync"
                    )

                if run_type is not None:
                    span.set_attribute("run_type", run_type)

                inputs = _SpanUtils.format_args_for_trace_json(
                    inspect.signature(func), *args, **kwargs
                )
                if input_processor:
                    processed_inputs = input_processor(json.loads(inputs))
                    inputs = json.dumps(processed_inputs, default=str)
                span.set_attribute("input.mime_type", "application/json")
                span.set_attribute("input.value", inputs)

                outputs = []
                for item in func(*args, **kwargs):
                    outputs.append(item)
                    span.add_event(f"Yielded: {item}")
                    yield item
                output = output_processor(outputs) if output_processor else outputs
                span.set_attribute(
                    "output.value", _SpanUtils.format_object_for_trace_json(output)
                )
                span.set_attribute("output.mime_type", "application/json")
            except Exception as e:
                span.record_exception(e)
                span.set_status(
                    trace.status.Status(trace.status.StatusCode.ERROR, str(e))
                )
                raise
            finally:
                _active_traced_span.reset(token)
                if span_cm:
                    span_cm.__exit__(None, None, None)

        # --------- Async generator wrapper ---------
        @wraps(func)
        async def async_generator_wrapper(*args, **kwargs):
            span_cm, span = get_span()
            token = _active_traced_span.set(span)
            try:
                # Check if this should be treated as a tool call
                is_tool = span_type and span_type.upper() == "TOOL"

                if is_tool:
                    # Set OpenInference tool call attributes
                    span.set_attribute("openinference.span.kind", "TOOL")
                    span.set_attribute("tool.name", trace_name)
                    span.set_attribute("span_type", "TOOL")
                else:
                    span.set_attribute(
                        "span_type", span_type or "function_call_generator_async"
                    )

                if run_type is not None:
                    span.set_attribute("run_type", run_type)

                inputs = _SpanUtils.format_args_for_trace_json(
                    inspect.signature(func), *args, **kwargs
                )
                if input_processor:
                    processed_inputs = input_processor(json.loads(inputs))
                    inputs = json.dumps(processed_inputs, default=str)
                span.set_attribute("input.mime_type", "application/json")
                span.set_attribute("input.value", inputs)

                outputs = []
                async for item in func(*args, **kwargs):
                    outputs.append(item)
                    span.add_event(f"Yielded: {item}")
                    yield item
                output = output_processor(outputs) if output_processor else outputs
                span.set_attribute(
                    "output.value", _SpanUtils.format_object_for_trace_json(output)
                )
                span.set_attribute("output.mime_type", "application/json")
            except Exception as e:
                span.record_exception(e)
                span.set_status(
                    trace.status.Status(trace.status.StatusCode.ERROR, str(e))
                )
                raise
            finally:
                _active_traced_span.reset(token)
                if span_cm:
                    span_cm.__exit__(None, None, None)

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        elif inspect.isgeneratorfunction(func):
            return generator_wrapper
        elif inspect.isasyncgenfunction(func):
            return async_generator_wrapper
        else:
            return sync_wrapper

    return decorator


def _get_supported_params(tracer_impl, params):
    """Extract the parameters supported by the tracer implementation.

    Args:
        tracer_impl: The tracer implementation function or callable
        params: Dictionary of parameters to check

    Returns:
        Dictionary containing only parameters supported by the tracer implementation
    """
    supported_params = {}
    if hasattr(tracer_impl, "__code__"):
        # For regular functions
        impl_signature = inspect.signature(tracer_impl)
        for param_name, param_value in params.items():
            if param_name in impl_signature.parameters and param_value is not None:
                supported_params[param_name] = param_value
    elif callable(tracer_impl):
        # For callable objects
        impl_signature = inspect.signature(tracer_impl.__call__)
        for param_name, param_value in params.items():
            if param_name in impl_signature.parameters and param_value is not None:
                supported_params[param_name] = param_value
    else:
        # If we can't inspect, pass all parameters and let the function handle it
        supported_params = params

    return supported_params


def traced(
    name: Optional[str] = None,
    run_type: Optional[str] = None,
    span_type: Optional[str] = None,
    input_processor: Optional[Callable[..., Any]] = None,
    output_processor: Optional[Callable[..., Any]] = None,
    hide_input: bool = False,
    hide_output: bool = False,
    recording: bool = True,
):
    """Decorator that will trace function invocations.

    Args:
        name: Optional name for the span
        run_type: Optional string to categorize the run type
        span_type: Optional string to categorize the span type. If set to "tool" or "TOOL",
                   the function is treated as an OpenInference tool call by setting:
                   - openinference.span.kind = "TOOL"
                   - tool.name = function name
                   - span_type = "TOOL"
                   - input.value and output.value (already set by default)
                   This makes the span compatible with evaluation helpers that extract tool calls from traces.
        input_processor: Optional function to process function inputs before recording
            Should accept a dictionary of inputs and return a processed dictionary
        output_processor: Optional function to process function outputs before recording
            Should accept the function output and return a processed value
        hide_input: If True, don't log any input data
        hide_output: If True, don't log any output data
        recording: If False, current span and all child spans are not captured regardless of their recording status
    """
    # Apply default processors selectively based on hide flags
    if hide_input:
        input_processor = _default_input_processor
    if hide_output:
        output_processor = _default_output_processor

    # Store the parameters for later reapplication
    params = {
        "name": name,
        "run_type": run_type,
        "span_type": span_type,
        "input_processor": input_processor,
        "output_processor": output_processor,
        "recording": recording,
    }

    # Check for custom implementation first
    custom_implementation = TracingManager.get_custom_tracer_implementation()
    tracer_impl: Any = (
        custom_implementation if custom_implementation else _opentelemetry_traced
    )

    def decorator(func):
        # Check which parameters are supported by the tracer_impl
        supported_params = _get_supported_params(tracer_impl, params)

        # Decorate the function with only supported parameters
        decorated_func = tracer_impl(**supported_params)(func)

        # Register both original and decorated function with parameters
        TracingManager.register_traced_function(func, decorated_func, params)
        return decorated_func

    return decorator
