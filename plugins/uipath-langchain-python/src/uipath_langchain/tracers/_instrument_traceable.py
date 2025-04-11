import functools
import importlib
import inspect
import logging
import sys
import uuid
from typing import Any, Dict, List, Literal, Optional

from langchain_core.callbacks import dispatch_custom_event

from ._events import CustomTraceEvents, FunctionCallEventData

# Original module and traceable function references
original_langsmith: Any = None
original_traceable: Any = None

logger = logging.getLogger(__name__)


def dispatch_trace_event(
    func_name,
    inputs: Dict[str, Any],
    event_type="call",
    call_uuid=None,
    result=None,
    exception=None,
    run_type: Optional[
        Literal["tool", "chain", "llm", "retriever", "embedding", "prompt", "parser"]
    ] = None,
    tags: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
):
    """Dispatch trace event to our server."""

    event_data = FunctionCallEventData(
        function_name=func_name,
        event_type=event_type,
        inputs=inputs,
        call_uuid=call_uuid,
        output=result,
        error=str(exception) if exception else None,
        run_type=run_type,
        tags=tags,
        metadata=metadata,
    )
    dispatch_custom_event(CustomTraceEvents.UIPATH_TRACE_FUNCTION_CALL, event_data)


def format_args_for_trace(
    signature: inspect.Signature, *args: Any, **kwargs: Any
) -> Dict[str, Any]:
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
    except Exception as e:
        logger.warning(
            f"Error formatting arguments for trace: {e}. Using args and kwargs directly."
        )
        return {"args": args, "kwargs": kwargs}


# Create patched version of traceable
def patched_traceable(*decorator_args, **decorator_kwargs):
    # Handle the case when @traceable is used directly as decorator without arguments
    if (
        len(decorator_args) == 1
        and callable(decorator_args[0])
        and not decorator_kwargs
    ):
        func = decorator_args[0]
        return _create_appropriate_wrapper(func, original_traceable(func), {})

    # Handle the case when @traceable(args) is used with parameters
    original_decorated = original_traceable(*decorator_args, **decorator_kwargs)

    def uipath_trace_decorator(func):
        # Apply the original decorator with its arguments
        wrapped_func = original_decorated(func)
        return _create_appropriate_wrapper(func, wrapped_func, decorator_kwargs)

    return uipath_trace_decorator


def _create_appropriate_wrapper(
    original_func: Any, wrapped_func: Any, decorator_kwargs: Dict[str, Any]
):
    """Create the appropriate wrapper based on function type."""

    # Get the function name and tags from decorator arguments
    func_name = decorator_kwargs.get("name", original_func.__name__)
    tags = decorator_kwargs.get("tags", None)
    metadata = decorator_kwargs.get("metadata", None)
    run_type = decorator_kwargs.get("run_type", None)

    # Async generator function
    if inspect.isasyncgenfunction(wrapped_func):

        @functools.wraps(wrapped_func)
        async def async_gen_wrapper(*args, **kwargs):
            try:
                call_uuid = str(uuid.uuid4())

                inputs = format_args_for_trace(
                    inspect.signature(original_func), *args, **kwargs
                )

                dispatch_trace_event(
                    func_name,
                    inputs,
                    "call",
                    call_uuid,
                    run_type=run_type,
                    tags=tags,
                    metadata=metadata,
                )
                async_gen = wrapped_func(*args, **kwargs)

                results = []

                async for item in async_gen:
                    results.append(item)
                    yield item

                dispatch_trace_event(
                    func_name, inputs, "completion", call_uuid, results
                )
            except Exception as e:
                dispatch_trace_event(
                    func_name, inputs, "completion", call_uuid, exception=e
                )
                raise

        return async_gen_wrapper

    # Sync generator function
    elif inspect.isgeneratorfunction(wrapped_func):

        @functools.wraps(wrapped_func)
        def gen_wrapper(*args, **kwargs):
            try:
                call_uuid = str(uuid.uuid4())

                inputs = format_args_for_trace(
                    inspect.signature(original_func), *args, **kwargs
                )

                results = []

                dispatch_trace_event(
                    func_name,
                    inputs,
                    "call",
                    call_uuid,
                    run_type=run_type,
                    tags=tags,
                    metadata=metadata,
                )
                gen = wrapped_func(*args, **kwargs)
                for item in gen:
                    results.append(item)
                    yield item
                dispatch_trace_event(
                    func_name, inputs, "completion", call_uuid, results
                )
            except Exception as e:
                dispatch_trace_event(
                    func_name, inputs, "completion", call_uuid, exception=e
                )
                raise

        return gen_wrapper

    # Async function
    elif inspect.iscoroutinefunction(wrapped_func):

        @functools.wraps(wrapped_func)
        async def async_wrapper(*args, **kwargs):
            try:
                call_uuid = str(uuid.uuid4())

                inputs = format_args_for_trace(
                    inspect.signature(original_func), *args, **kwargs
                )

                dispatch_trace_event(
                    func_name,
                    inputs,
                    "call",
                    call_uuid,
                    run_type=run_type,
                    tags=tags,
                    metadata=metadata,
                )
                result = await wrapped_func(*args, **kwargs)
                dispatch_trace_event(func_name, inputs, "completion", call_uuid, result)
                return result
            except Exception as e:
                dispatch_trace_event(
                    func_name, inputs, "completion", call_uuid, exception=e
                )
                raise

        return async_wrapper

    # Regular sync function (default case)
    else:

        @functools.wraps(wrapped_func)
        def sync_wrapper(*args, **kwargs):
            try:
                call_uuid = str(uuid.uuid4())

                inputs = format_args_for_trace(
                    inspect.signature(original_func), *args, **kwargs
                )

                dispatch_trace_event(
                    func_name,
                    inputs,
                    "call",
                    call_uuid,
                    run_type=run_type,
                    tags=tags,
                    metadata=metadata,
                )
                result = wrapped_func(*args, **kwargs)
                dispatch_trace_event(func_name, inputs, "completion", call_uuid, result)
                return result
            except Exception as e:
                dispatch_trace_event(
                    func_name, inputs, "completion", call_uuid, exception=e
                )
                raise

        return sync_wrapper


# Apply the patch
def _instrument_traceable():
    """Apply the patch to langsmith module at import time."""
    global original_langsmith, original_traceable

    # Import the original module if not already done
    if original_langsmith is None:
        # Temporarily remove our custom module from sys.modules
        if "langsmith" in sys.modules:
            original_langsmith = sys.modules["langsmith"]
            del sys.modules["langsmith"]

        # Import the original module
        original_langsmith = importlib.import_module("langsmith")

        # Store the original traceable
        original_traceable = original_langsmith.traceable

        # Replace the traceable function with our patched version
        original_langsmith.traceable = patched_traceable

        # Put our modified module back
        sys.modules["langsmith"] = original_langsmith

    return original_langsmith
