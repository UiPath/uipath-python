"""Tracing decorators for function instrumentation."""

import inspect
import logging
import random
from functools import wraps
from typing import Any, Callable, Optional, overload

from opentelemetry import context as context_api
from opentelemetry import trace
from opentelemetry.context import _SUPPRESS_INSTRUMENTATION_KEY
from opentelemetry.trace import SpanContext, TraceFlags
from opentelemetry.trace.status import StatusCode

from uipath.core.tracing._utils import (
    get_supported_params,
    set_span_input_attributes,
    set_span_output_attributes,
)
from uipath.core.tracing.span_utils import (
    ParentedNonRecordingSpan,
    UiPathSpanUtils,
    _span_registry,
)

logger = logging.getLogger(__name__)


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

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        trace_name = name or func.__name__

        def get_span():
            ctx = UiPathSpanUtils.get_parent_context()
            if not recording:
                parent_context = trace.get_current_span(ctx).get_span_context()

                # Create a valid but non-sampled trace context
                # Generate a valid trace ID (not INVALID)
                trace_id = random.getrandbits(128)
                span_id = random.getrandbits(64)

                non_sampled_context = SpanContext(
                    trace_id=trace_id,
                    span_id=span_id,
                    is_remote=False,
                    trace_flags=TraceFlags(0x00),  # NOT sampled
                )
                non_recording = ParentedNonRecordingSpan(
                    non_sampled_context, parent=parent_context
                )

                # Make it active so children see it
                span_cm = trace.use_span(non_recording)
                span_cm.__enter__()

                _span_registry.register_span(non_recording)

                return span_cm, non_recording
            else:
                # Normal recording span
                span_cm = trace.get_tracer(__name__).start_as_current_span(
                    trace_name, context=ctx
                )
                span = span_cm.__enter__()
                return span_cm, span

        # --------- Sync wrapper ---------
        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            if context_api.get_value(_SUPPRESS_INSTRUMENTATION_KEY):
                return func(*args, **kwargs)
            span_cm, span = get_span()
            try:
                # Set input attributes BEFORE execution
                set_span_input_attributes(
                    span,
                    trace_name=trace_name,
                    wrapped_func=func,
                    args=args,
                    kwargs=kwargs,
                    run_type=run_type,
                    span_type=span_type or "function_call_sync",
                    input_processor=input_processor,
                )

                # Execute the function
                result = func(*args, **kwargs)

                # Set output attributes AFTER execution
                set_span_output_attributes(
                    span,
                    result=result,
                    output_processor=output_processor,
                )
                return result
            except Exception as e:
                span.record_exception(e)
                span.set_status(StatusCode.ERROR, str(e))
                raise
            finally:
                if span_cm:
                    span_cm.__exit__(None, None, None)

        # --------- Async wrapper ---------
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            if context_api.get_value(_SUPPRESS_INSTRUMENTATION_KEY):
                return await func(*args, **kwargs)
            span_cm, span = get_span()
            try:
                # Set input attributes BEFORE execution
                set_span_input_attributes(
                    span,
                    trace_name=trace_name,
                    wrapped_func=func,
                    args=args,
                    kwargs=kwargs,
                    run_type=run_type,
                    span_type=span_type or "function_call_async",
                    input_processor=input_processor,
                )

                # Execute the function
                result = await func(*args, **kwargs)

                # Set output attributes AFTER execution
                set_span_output_attributes(
                    span,
                    result=result,
                    output_processor=output_processor,
                )
                return result
            except Exception as e:
                span.record_exception(e)
                span.set_status(StatusCode.ERROR, str(e))
                raise
            finally:
                if span_cm:
                    span_cm.__exit__(None, None, None)

        # --------- Generator wrapper ---------
        @wraps(func)
        def generator_wrapper(*args: Any, **kwargs: Any) -> Any:
            if context_api.get_value(_SUPPRESS_INSTRUMENTATION_KEY):
                for item in func(*args, **kwargs):
                    yield item
                return
            span_cm, span = get_span()
            try:
                # Set input attributes BEFORE execution
                set_span_input_attributes(
                    span,
                    trace_name=trace_name,
                    wrapped_func=func,
                    args=args,
                    kwargs=kwargs,
                    run_type=run_type,
                    span_type=span_type or "function_call_generator_sync",
                    input_processor=input_processor,
                )

                # Execute the generator and collect outputs
                outputs = []
                for item in func(*args, **kwargs):
                    outputs.append(item)
                    span.add_event(f"Yielded: {item}")
                    yield item

                # Set output attributes AFTER execution
                set_span_output_attributes(
                    span,
                    result=outputs,
                    output_processor=output_processor,
                )
            except Exception as e:
                span.record_exception(e)
                span.set_status(StatusCode.ERROR, str(e))
                raise
            finally:
                if span_cm:
                    span_cm.__exit__(None, None, None)

        # --------- Async generator wrapper ---------
        @wraps(func)
        async def async_generator_wrapper(*args: Any, **kwargs: Any) -> Any:
            if context_api.get_value(_SUPPRESS_INSTRUMENTATION_KEY):
                async for item in func(*args, **kwargs):
                    yield item
                return
            span_cm, span = get_span()
            try:
                # Set input attributes BEFORE execution
                set_span_input_attributes(
                    span,
                    trace_name=trace_name,
                    wrapped_func=func,
                    args=args,
                    kwargs=kwargs,
                    run_type=run_type,
                    span_type=span_type or "function_call_generator_async",
                    input_processor=input_processor,
                )

                # Execute the generator and collect outputs
                outputs = []
                async for item in func(*args, **kwargs):
                    outputs.append(item)
                    span.add_event(f"Yielded: {item}")
                    yield item

                # Set output attributes AFTER execution
                set_span_output_attributes(
                    span,
                    result=outputs,
                    output_processor=output_processor,
                )
            except Exception as e:
                span.record_exception(e)
                span.set_status(StatusCode.ERROR, str(e))
                raise
            finally:
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


@overload
def traced(func: Callable[..., Any], /) -> Callable[..., Any]: ...


@overload
def traced(
    name: Optional[str] = ...,
    run_type: Optional[str] = ...,
    span_type: Optional[str] = ...,
    input_processor: Optional[Callable[..., Any]] = ...,
    output_processor: Optional[Callable[..., Any]] = ...,
    hide_input: bool = ...,
    hide_output: bool = ...,
    recording: bool = ...,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]: ...


def traced(
    name: Optional[str | Callable[..., Any]] = None,
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
        name: Optional custom name for the span
        run_type: Optional string to categorize the run type
        span_type: Optional string to categorize the span type
        input_processor: Optional function to process function inputs before recording
            Should accept a dictionary of inputs and return a processed dictionary
        output_processor: Optional function to process function outputs before recording
            Should accept the function output and return a processed value
        hide_input: If True, don't log any input data
        hide_output: If True, don't log any output data
        recording: If False, current span and all child spans are not captured
    """
    # Handle @traced without parentheses: the decorated function
    # is passed as the first positional argument (``name``).
    _func: Optional[Callable[..., Any]] = None
    if callable(name):
        _func = name
        name = None

    # Apply default processors selectively based on hide flags
    def _default_input_processor(inputs: Any) -> dict[str, str]:
        """Default input processor that doesn't log any actual input data."""
        return {"redacted": "Input data not logged for privacy/security"}

    def _default_output_processor(outputs: Any) -> dict[str, str]:
        """Default output processor that doesn't log any actual output data."""
        return {"redacted": "Output data not logged for privacy/security"}

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

    tracer_impl = _opentelemetry_traced

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        # Check which parameters are supported by the tracer_impl
        supported_params = get_supported_params(tracer_impl, params)

        # Decorate the function with only supported parameters
        decorated_func = tracer_impl(**supported_params)(func)

        return decorated_func

    if _func is not None:
        return decorator(_func)

    return decorator


__all__ = ["traced"]
