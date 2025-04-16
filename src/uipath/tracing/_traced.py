import inspect
import json
import logging
from functools import wraps
from typing import Any, Callable, Optional

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from ._otel_exporters import LlmOpsHttpExporter
from ._utils import _SpanUtils

logger = logging.getLogger(__name__)

trace.set_tracer_provider(TracerProvider())
trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(LlmOpsHttpExporter()))  # type: ignore
tracer = trace.get_tracer(__name__)


def wait_for_tracers():
    """Wait for all tracers to finish."""
    trace.get_tracer_provider().shutdown()  # type: ignore


def _default_input_processor(inputs):
    """Default input processor that doesn't log any actual input data."""
    return {"redacted": "Input data not logged for privacy/security"}


def _default_output_processor(outputs):
    """Default output processor that doesn't log any actual output data."""
    return {"redacted": "Output data not logged for privacy/security"}


class TracedDecoratorRegistry:
    """Registry for tracing decorators."""

    _decorators: dict[str, Any] = {}
    _active_decorator = "opentelemetry"

    @classmethod
    def register_decorator(cls, name, decorator_factory):
        """Register a decorator factory function with a name."""
        cls._decorators[name] = decorator_factory
        cls._active_decorator = name
        return cls

    @classmethod
    def get_decorator(cls):
        """Get the currently active decorator factory."""
        return cls._decorators.get(cls._active_decorator)


def _opentelemetry_traced(
    run_type: Optional[str] = None,
    span_type: Optional[str] = None,
    input_processor: Optional[Callable[..., Any]] = None,
    output_processor: Optional[Callable[..., Any]] = None,
):
    def decorator(func):
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            with tracer.start_as_current_span(func.__name__) as span:
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
            with tracer.start_as_current_span(func.__name__) as span:
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
            with tracer.start_as_current_span(func.__name__) as span:
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
            with tracer.start_as_current_span(func.__name__) as span:
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


def traced(
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

    decorator_factory = TracedDecoratorRegistry.get_decorator()

    if decorator_factory:
        return decorator_factory(run_type, span_type, input_processor, output_processor)
    else:
        # Fallback to original implementation if no active decorator
        return _opentelemetry_traced(
            run_type, span_type, input_processor, output_processor
        )
