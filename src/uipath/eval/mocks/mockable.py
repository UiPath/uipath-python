"""Mockable interface."""

import asyncio
import functools
import inspect
import logging
import threading
from typing import Any

from opentelemetry import trace
from pydantic import TypeAdapter
from pydantic_function_models import (  # type: ignore[import-untyped]
    ValidatedFunction,
)
from uipath.core import UiPathSpanUtils

from ._mocker import UiPathNoMockFoundError
from ._mocks import get_mocked_response
from ._types import ExampleCall

_event_loop = None
logger = logging.getLogger(__name__)

MOCKED_ANNOTATION_KEY = "__uipath_response_mocked"


def run_coroutine(coro):
    """Run a coroutine synchronously."""
    global _event_loop
    if not _event_loop or not _event_loop.is_running():
        _event_loop = asyncio.new_event_loop()
        threading.Thread(target=_event_loop.run_forever, daemon=True).start()
    future = asyncio.run_coroutine_threadsafe(coro, _event_loop)
    return future.result()


def mocked_response_decorator(func, params: dict[str, Any]):
    """Mocked response decorator."""

    async def mock_response_generator(*args, **kwargs):
        mocked_response = await get_mocked_response(func, params, *args, **kwargs)

        # Mocking successful.
        context = UiPathSpanUtils.get_parent_context()
        span = trace.get_current_span(context=context)
        span.set_attribute(MOCKED_ANNOTATION_KEY, True)

        return_type: Any = func.__annotations__.get("return", None)

        if return_type is not None:
            mocked_response = TypeAdapter(return_type).validate_python(mocked_response)
        return mocked_response

    is_async = inspect.iscoroutinefunction(func)
    if is_async:

        @functools.wraps(func)
        async def decorated_func(*args, **kwargs):
            try:
                return await mock_response_generator(*args, **kwargs)
            except UiPathNoMockFoundError:
                return await func(*args, **kwargs)
    else:

        @functools.wraps(func)
        def decorated_func(*args, **kwargs):
            try:
                return run_coroutine(mock_response_generator(*args, **kwargs))
            except UiPathNoMockFoundError:
                return func(*args, **kwargs)

    return decorated_func


def get_output_schema(func):
    """Retrieves the JSON schema for a function's return type hint."""
    try:
        adapter = TypeAdapter(inspect.signature(func).return_annotation)
        return adapter.json_schema()
    except Exception:
        logger.warning(f"Unable to extract output schema for function {func.__name__}")
        return {}


def get_input_schema(func):
    """Retrieves the JSON schema for a function's input type."""
    try:
        return ValidatedFunction(func).model.model_json_schema()
    except Exception:
        logger.warning(f"Unable to extract input schema for function {func.__name__}")
        return {}


def mockable(
    name: str | None = None,
    description: str | None = None,
    input_schema: dict[str, Any] | None = None,
    output_schema: dict[str, Any] | None = None,
    example_calls: list[ExampleCall] | None = None,
    **kwargs,
):
    """Decorate a function to be a mockable."""

    def decorator(func):
        params = {
            "name": name or func.__name__,
            "description": description or func.__doc__,
            "input_schema": input_schema or get_input_schema(func),
            "output_schema": output_schema or get_output_schema(func),
            "example_calls": example_calls,
            **kwargs,
        }
        return mocked_response_decorator(func, params)

    return decorator
