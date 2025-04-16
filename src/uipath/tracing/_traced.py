import inspect
import json
import logging
from functools import wraps
from typing import Any

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


def _opentelemetry_traced():
    def decorator(func):
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            with tracer.start_as_current_span(func.__name__) as span:
                span.set_attribute("span_type", "function_call_sync")
                span.set_attribute(
                    "inputs",
                    _SpanUtils.format_args_for_trace_json(
                        inspect.signature(func), *args, **kwargs
                    ),
                )
                try:
                    result = func(*args, **kwargs)
                    span.set_attribute(
                        "output", json.dumps(result, default=str)
                    )  # Record output
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
                span.set_attribute("span_type", "function_call_async")
                span.set_attribute(
                    "inputs",
                    _SpanUtils.format_args_for_trace_json(
                        inspect.signature(func), *args, **kwargs
                    ),
                )
                try:
                    result = await func(*args, **kwargs)
                    span.set_attribute(
                        "output", json.dumps(result, default=str)
                    )  # Record output
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
                span.set_attribute("span_type", "function_call_generator_sync")
                span.set_attribute(
                    "inputs",
                    _SpanUtils.format_args_for_trace_json(
                        inspect.signature(func), *args, **kwargs
                    ),
                )
                outputs = []
                try:
                    for item in func(*args, **kwargs):
                        outputs.append(item)
                        span.add_event(f"Yielded: {item}")  # Add event for each yield
                        yield item
                    span.set_attribute(
                        "output", json.dumps(outputs, default=str)
                    )  # Record aggregated outputs
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(
                        trace.status.Status(trace.status.StatusCode.ERROR, str(e))
                    )
                    raise

        @wraps(func)
        async def async_generator_wrapper(*args, **kwargs):
            with tracer.start_as_current_span(func.__name__) as span:
                span.set_attribute("span_type", "function_call_generator_async")
                span.set_attribute(
                    "inputs",
                    _SpanUtils.format_args_for_trace_json(
                        inspect.signature(func), *args, **kwargs
                    ),
                )
                outputs = []
                try:
                    async for item in func(*args, **kwargs):
                        outputs.append(item)
                        span.add_event(f"Yielded: {item}")  # Add event for each yield
                        yield item
                    span.set_attribute(
                        "output", json.dumps(outputs, default=str)
                    )  # Record aggregated outputs
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


def traced():
    """Decorator that will trace function invocations."""
    decorator_factory = TracedDecoratorRegistry.get_decorator()

    if decorator_factory:
        return decorator_factory()
    else:
        # Fallback to original implementation if no active decorator
        return _opentelemetry_traced()
