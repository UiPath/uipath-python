"""Mocking interface."""

import logging
from contextvars import ContextVar
from typing import Any, Callable, Optional

from uipath._cli._evals._models._evaluation_set import EvaluationItem
from uipath._cli._evals._span_collection import ExecutionSpanCollector
from uipath._cli._evals.mocks.cache_manager import CacheManager
from uipath._cli._evals.mocks.mocker import Mocker, UiPathNoMockFoundError
from uipath._cli._evals.mocks.mocker_factory import MockerFactory

# Context variables for evaluation items and mockers
evaluation_context: ContextVar[Optional[EvaluationItem]] = ContextVar(
    "evaluation", default=None
)

mocker_context: ContextVar[Optional[Mocker]] = ContextVar("mocker", default=None)

# Span collector for trace access during mocking
span_collector_context: ContextVar[Optional[ExecutionSpanCollector]] = ContextVar(
    "span_collector", default=None
)

# Execution ID for the current evaluation item
execution_id_context: ContextVar[Optional[str]] = ContextVar(
    "execution_id", default=None
)

# Cache manager for LLM and input mocker responses
cache_manager_context: ContextVar[Optional[CacheManager]] = ContextVar(
    "cache_manager", default=None
)

logger = logging.getLogger(__name__)


def set_execution_context(
    eval_item: EvaluationItem,
    span_collector: ExecutionSpanCollector,
    execution_id: str,
) -> None:
    """Set the execution context for an evaluation run for mocking and trace access."""
    evaluation_context.set(eval_item)

    try:
        if eval_item.mocking_strategy:
            mocker_context.set(MockerFactory.create(eval_item))
        else:
            mocker_context.set(None)
    except Exception:
        logger.warning(f"Failed to create mocker for evaluation {eval_item.name}")
        mocker_context.set(None)

    span_collector_context.set(span_collector)
    execution_id_context.set(execution_id)


def clear_execution_context() -> None:
    """Clear the execution context after evaluation completes."""
    evaluation_context.set(None)
    mocker_context.set(None)
    span_collector_context.set(None)
    execution_id_context.set(None)


async def get_mocked_response(
    func: Callable[[Any], Any], params: dict[str, Any], *args, **kwargs
) -> Any:
    """Get a mocked response."""
    mocker = mocker_context.get()
    if mocker is None:
        raise UiPathNoMockFoundError()
    else:
        return await mocker.response(func, params, *args, **kwargs)
