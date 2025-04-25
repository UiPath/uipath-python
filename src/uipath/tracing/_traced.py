import importlib
import inspect
import json
import logging
from functools import wraps
from typing import Any, Callable, List, Optional, Tuple

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from ._otel_exporters import LlmOpsHttpExporter
from ._utils import _SpanUtils

logger = logging.getLogger(__name__)

trace.set_tracer_provider(TracerProvider())
trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(LlmOpsHttpExporter()))  # type: ignore
tracer = trace.get_tracer(__name__)


class TracingManager:
    """Static utility class to manage tracing implementations and decorated functions."""

    # Registry to track original functions, decorated functions, and their parameters
    # Each entry is (original_func, decorated_func, params)
    _traced_registry: List[Tuple[Callable[..., Any], Callable[..., Any], Any]] = []

    # Custom tracer implementation
    _custom_tracer_implementation = None

    @classmethod
    def get_custom_tracer_implementation(cls):
        """Get the currently set custom tracer implementation."""
        return cls._custom_tracer_implementation

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
):
    """Default tracer implementation using OpenTelemetry."""

    def decorator(func):
        trace_name = name if name is not None else func.__name__

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            with tracer.start_as_current_span(trace_name) as span:
                default_span_type = "function_call_sync"
                span.set_attribute(
                    "span_type",
                    span_type if span_type is not None else default_span_type,
                )
                if run_type is not None:
                    span.set_attribute("run_type", run_type)

                # Format arguments for tracing
                inputs = _SpanUtils.format_args_for_trace_json(
                    inspect.signature(func), *args, **kwargs
                )
                # Apply input processor if provided
                if input_processor is not None:
                    processed_inputs = input_processor(json.loads(inputs))
                    inputs = json.dumps(processed_inputs, default=str)
                span.set_attribute("inputs", inputs)
                try:
                    result = func(*args, **kwargs)
                    # Process output if processor is provided
                    output = result
                    if output_processor is not None:
                        output = output_processor(result)
                    span.set_attribute("output", json.dumps(output, default=str))
                    return result
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(
                        trace.status.Status(trace.status.StatusCode.ERROR, str(e))
                    )
                    raise

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            with tracer.start_as_current_span(trace_name) as span:
                default_span_type = "function_call_async"
                span.set_attribute(
                    "span_type",
                    span_type if span_type is not None else default_span_type,
                )
                if run_type is not None:
                    span.set_attribute("run_type", run_type)

                # Format arguments for tracing
                inputs = _SpanUtils.format_args_for_trace_json(
                    inspect.signature(func), *args, **kwargs
                )
                # Apply input processor if provided
                if input_processor is not None:
                    processed_inputs = input_processor(json.loads(inputs))
                    inputs = json.dumps(processed_inputs, default=str)
                span.set_attribute("inputs", inputs)
                try:
                    result = await func(*args, **kwargs)
                    # Process output if processor is provided
                    output = result
                    if output_processor is not None:
                        output = output_processor(result)
                    span.set_attribute("output", json.dumps(output, default=str))
                    return result
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(
                        trace.status.Status(trace.status.StatusCode.ERROR, str(e))
                    )
                    raise

        @wraps(func)
        def generator_wrapper(*args, **kwargs):
            with tracer.start_as_current_span(trace_name) as span:
                default_span_type = "function_call_generator_sync"
                span.set_attribute(
                    "span_type",
                    span_type if span_type is not None else default_span_type,
                )
                if run_type is not None:
                    span.set_attribute("run_type", run_type)

                # Format arguments for tracing
                inputs = _SpanUtils.format_args_for_trace_json(
                    inspect.signature(func), *args, **kwargs
                )
                # Apply input processor if provided
                if input_processor is not None:
                    processed_inputs = input_processor(json.loads(inputs))
                    inputs = json.dumps(processed_inputs, default=str)
                span.set_attribute("inputs", inputs)
                outputs = []
                try:
                    for item in func(*args, **kwargs):
                        outputs.append(item)
                        span.add_event(f"Yielded: {item}")  # Add event for each yield
                        yield item

                    # Process output if processor is provided
                    output_to_record = outputs
                    if output_processor is not None:
                        output_to_record = output_processor(outputs)
                    span.set_attribute(
                        "output", json.dumps(output_to_record, default=str)
                    )
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(
                        trace.status.Status(trace.status.StatusCode.ERROR, str(e))
                    )
                    raise

        @wraps(func)
        async def async_generator_wrapper(*args, **kwargs):
            with tracer.start_as_current_span(trace_name) as span:
                default_span_type = "function_call_generator_async"
                span.set_attribute(
                    "span_type",
                    span_type if span_type is not None else default_span_type,
                )
                if run_type is not None:
                    span.set_attribute("run_type", run_type)

                # Format arguments for tracing
                inputs = _SpanUtils.format_args_for_trace_json(
                    inspect.signature(func), *args, **kwargs
                )
                # Apply input processor if provided
                if input_processor is not None:
                    processed_inputs = input_processor(json.loads(inputs))
                    inputs = json.dumps(processed_inputs, default=str)
                span.set_attribute("inputs", inputs)
                outputs = []
                try:
                    async for item in func(*args, **kwargs):
                        outputs.append(item)
                        span.add_event(f"Yielded: {item}")  # Add event for each yield
                        yield item

                    # Process output if processor is provided
                    output_to_record = outputs
                    if output_processor is not None:
                        output_to_record = output_processor(outputs)
                    span.set_attribute(
                        "output", json.dumps(output_to_record, default=str)
                    )
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(
                        trace.status.Status(trace.status.StatusCode.ERROR, str(e))
                    )
                    raise

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
):
    """Decorator that will trace function invocations.

    Args:
        run_type: Optional string to categorize the run type
        span_type: Optional string to categorize the span type
        input_processor: Optional function to process function inputs before recording
            Should accept a dictionary of inputs and return a processed dictionary
        output_processor: Optional function to process function outputs before recording
            Should accept the function output and return a processed value
        hide_input: If True, don't log any input data
        hide_output: If True, don't log any output data
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
