"""Mocking interface."""

import asyncio
import functools
import inspect
import logging
import threading
from contextvars import ContextVar
from typing import Any, Callable, Optional

from pydantic import TypeAdapter
from pydantic_function_models import ValidatedFunction  # type: ignore[import-untyped]

from uipath._cli._evals._models._evaluation_set import EvaluationItem
from uipath._cli._evals.mocks.mocker import Mocker
from uipath._cli._evals.mocks.mocker_factory import MockerFactory

evaluation_context: ContextVar[Optional[EvaluationItem]] = ContextVar(
    "evaluation", default=None
)

mocker_context: ContextVar[Optional[Mocker]] = ContextVar("mocker", default=None)


def set_evaluation_item(item: EvaluationItem) -> None:
    """Set an evaluation item within an evaluation set."""
    evaluation_context.set(item)
    try:
        mocker_context.set(MockerFactory.create(item))
    except Exception:
        logger.warning(f"Failed to create mocker for evaluation {item.name}")
        mocker_context.set(None)


async def get_mocked_response(
    func: Callable[[Any], Any], params: dict[str, Any], *args, **kwargs
) -> Any:
    """Get a mocked response."""
    mocker = mocker_context.get()
    evaluation_item = evaluation_context.get()
    if mocker is None or evaluation_item is None:
        # TODO raise a new UiPath exception type
        raise RuntimeError(f"Evaluation item {func.__name__} has not been evaluated")
    else:
        return await mocker.response(func, params, *args, **kwargs)


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
            except Exception:
                logger.warning(
                    f"Failed to mock response for {func.__name__}. Falling back to func."
                )
                return await func(*args, **kwargs)
    else:

        @functools.wraps(func)
        def decorated_func(*args, **kwargs):
            try:
                return run_coroutine(mock_response_generator(*args, **kwargs))
            except Exception:
                logger.warning(
                    f"Failed to mock response for {func.__name__}. Falling back to func."
                )
                return func(*args, **kwargs)

    return decorated_func


def mockable(
    name: Optional[str] = None,
    description: Optional[str] = None,
    **kwargs,
):
    """Decorate a function to be a mockable."""

    def decorator(func):
        params = {
            "name": name or func.__name__,
            "description": description or func.__doc__,
            "input_schema": get_input_schema(func),
            "output_schema": get_output_schema(func),
            **kwargs,
        }
        return mocked_response_decorator(func, params)

    return decorator


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
