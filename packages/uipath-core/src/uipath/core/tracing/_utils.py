"""Helper utilities for the tracing module."""

import inspect
import json
from collections.abc import Callable
from typing import Any, Mapping, Optional

from opentelemetry.trace import Span

from uipath.core.serialization import serialize_json


def get_supported_params(
    tracer_impl: Callable[..., Any],
    params: Mapping[str, Any],
) -> dict[str, Any]:
    """Extract the parameters supported by the tracer implementation."""
    try:
        sig = inspect.signature(tracer_impl)
    except (TypeError, ValueError):
        # If we can't inspect, pass all parameters and let the function handle it
        return dict(params)

    supported: dict[str, Any] = {}
    for name, value in params.items():
        if value is not None and name in sig.parameters:
            supported[name] = value
    return supported


def format_args_for_trace_json(
    signature: inspect.Signature, *args: Any, **kwargs: Any
) -> str:
    """Return a JSON string of inputs from the function signature."""
    result = format_args_for_trace(signature, *args, **kwargs)
    return serialize_json(result)


def format_object_for_trace_json(
    input_object: Any,
) -> str:
    """Return a JSON string of inputs from the function signature."""
    return serialize_json(input_object)


def format_args_for_trace(
    signature: inspect.Signature, *args: Any, **kwargs: Any
) -> dict[str, Any]:
    try:
        """Return a dictionary of inputs from the function signature."""
        # Create a parameter mapping by partially binding the arguments

        parameter_binding = signature.bind_partial(*args, **kwargs)

        # Fill in default values for any unspecified parameters
        parameter_binding.apply_defaults()

        # Extract the input parameters, skipping special Python parameters
        result = {}
        for name, value in parameter_binding.arguments.items():
            # Skip class and instance references
            if name in ("self", "cls"):
                continue

            # Handle **kwargs parameters specially
            param_info = signature.parameters.get(name)
            if param_info and param_info.kind == inspect.Parameter.VAR_KEYWORD:
                # Flatten nested kwargs directly into the result
                if isinstance(value, dict):
                    result.update(value)
            else:
                # Regular parameter
                result[name] = value

        return result
    except Exception:
        return {"args": args, "kwargs": kwargs}


def set_span_input_attributes(
    span: Span,
    trace_name: str,
    wrapped_func: Callable[..., Any],
    args: Any,
    kwargs: Any,
    span_type: str,
    run_type: Optional[str],
    input_processor: Optional[Callable[..., Any]],
) -> None:
    """Set span attributes for metadata and inputs before function execution.

    This should be called BEFORE the wrapped function executes to ensure
    input context is captured even if the function raises an exception.

    Args:
        span: The OpenTelemetry span to set attributes on
        trace_name: Name of the trace/span
        wrapped_func: The function being traced
        args: Positional arguments passed to the function
        kwargs: Keyword arguments passed to the function
        span_type: Span type categorization (set to "TOOL" for OpenInference tool calls)
        run_type: Optional run type categorization
        input_processor: Optional function to process inputs before recording
    """
    is_tool = span_type and span_type.upper() == "TOOL"
    if is_tool:
        span.set_attribute("openinference.span.kind", "TOOL")
        span.set_attribute("tool.name", trace_name)
        span.set_attribute("span_type", "TOOL")
    else:
        span.set_attribute("span_type", span_type)

    if run_type is not None:
        span.set_attribute("run_type", run_type)

    inputs = format_args_for_trace_json(
        inspect.signature(wrapped_func), *args, **kwargs
    )
    if input_processor:
        processed_inputs = input_processor(json.loads(inputs))
        inputs = json.dumps(processed_inputs, default=str)
    span.set_attribute("input.mime_type", "application/json")
    span.set_attribute("input.value", inputs)


def set_span_output_attributes(
    span: Span,
    result: Any,
    output_processor: Optional[Callable[..., Any]],
) -> None:
    """Set span attributes for outputs after function execution.

    This should be called AFTER the wrapped function executes successfully.

    Args:
        span: The OpenTelemetry span to set attributes on
        result: The result from the function execution
        output_processor: Optional function to process outputs before recording
    """
    output = output_processor(result) if output_processor else result
    span.set_attribute("output.value", format_object_for_trace_json(output))
    span.set_attribute("output.mime_type", "application/json")
