"""Mocking interface."""

import logging
from contextvars import ContextVar
from typing import Any, Callable

from uipath._cli._evals._span_collection import ExecutionSpanCollector
from uipath._cli._evals.mocks.cache_manager import CacheManager
from uipath._cli._evals.mocks.mocker import Mocker, UiPathNoMockFoundError
from uipath._cli._evals.mocks.mocker_factory import MockerFactory
from uipath._cli._evals.mocks.types import (
    LLMMockingStrategy,
    MockingContext,
    MockitoMockingStrategy,
)

# Context variables for evaluation items and mockers
mocking_context: ContextVar[MockingContext | None] = ContextVar(
    "mocking_context", default=None
)

mocker_context: ContextVar[Mocker | None] = ContextVar("mocker", default=None)
# Span collector for trace access during mocking
span_collector_context: ContextVar[ExecutionSpanCollector | None] = ContextVar(
    "span_collector", default=None
)

# Execution ID for the current evaluation item
execution_id_context: ContextVar[str | None] = ContextVar("execution_id", default=None)

# Cache manager for LLM and input mocker responses
cache_manager_context: ContextVar[CacheManager | None] = ContextVar(
    "cache_manager", default=None
)

logger = logging.getLogger(__name__)


def set_execution_context(
    context: MockingContext | None,
    span_collector: ExecutionSpanCollector,
    execution_id: str | None = None,
) -> None:
    """Set the execution context for an evaluation run for mocking and trace access."""
    mocking_context.set(context)

    try:
        if context and context.strategy:
            mocker_context.set(MockerFactory.create(context))
        else:
            mocker_context.set(None)
    except Exception:
        logger.warning("Failed to create mocker.")
        mocker_context.set(None)

    span_collector_context.set(span_collector)
    execution_id_context.set(execution_id)


def clear_execution_context() -> None:
    """Clear the execution context after evaluation completes."""
    mocking_context.set(None)
    mocker_context.set(None)
    span_collector_context.set(None)
    execution_id_context.set(None)


def _normalize_tool_name(name: str) -> str:
    """Normalize tool name by replacing underscores with spaces.

    Tool names may use spaces in configuration but underscores in execution.
    """
    return name.replace("_", " ")


def is_tool_simulated(tool_name: str) -> bool:
    """Check if a tool will be simulated based on the current mocking strategy context.

    Args:
        tool_name: The name of the tool to check.

    Returns:
        True if we're in an mocking strategy context and the tool is configured
        to be simulated, False otherwise.
    """
    ctx = mocking_context.get()
    strategy = ctx.strategy if ctx else None
    if strategy is None:
        return False

    normalized_tool_name = _normalize_tool_name(tool_name)

    if isinstance(strategy, LLMMockingStrategy):
        simulated_names = [
            _normalize_tool_name(t.name) for t in strategy.tools_to_simulate
        ]
        return normalized_tool_name in simulated_names
    elif isinstance(strategy, MockitoMockingStrategy):
        return any(
            _normalize_tool_name(b.function) == normalized_tool_name
            for b in strategy.behaviors
        )

    return False


async def get_mocked_response(
    func: Callable[[Any], Any], params: dict[str, Any], *args, **kwargs
) -> Any:
    """Get a mocked response."""
    mocker = mocker_context.get()
    if mocker is None:
        raise UiPathNoMockFoundError()
    else:
        return await mocker.response(func, params, *args, **kwargs)
