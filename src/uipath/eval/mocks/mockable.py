"""Mockable interface."""

import asyncio
import functools
import inspect
import logging
import threading
from typing import Any, List, Optional

from pydantic import TypeAdapter
from pydantic_function_models import ValidatedFunction  # type: ignore[import-untyped]

from uipath._cli._evals._models._mocks import ExampleCall
from uipath._cli._evals.mocks.mocker import UiPathNoMockFoundError
from uipath._cli._evals.mocks.mocks import get_mocked_response

_event_loop = None
logger = logging.getLogger(__name__)


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
    name: Optional[str] = None,
    description: Optional[str] = None,
    input_schema: Optional[dict[str, Any]] = None,
    output_schema: Optional[dict[str, Any]] = None,
    example_calls: Optional[List[ExampleCall]] = None,
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
