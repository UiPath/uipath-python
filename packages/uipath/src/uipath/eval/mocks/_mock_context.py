"""Mocking interface."""

from contextvars import ContextVar
from typing import Any, Callable

from ._cache_manager import CacheManager
from ._mocker import Mocker, UiPathNoMockFoundError
from ._types import (
    LLMMockingStrategy,
    MockingContext,
    MockitoMockingStrategy,
)

# Context variables for evaluation items and mockers
mocking_context: ContextVar[MockingContext | None] = ContextVar(
    "mocking_context", default=None
)

mocker_context: ContextVar[Mocker | None] = ContextVar("mocker", default=None)

# Cache manager for LLM and input mocker responses
cache_manager_context: ContextVar[CacheManager | None] = ContextVar(
    "cache_manager", default=None
)


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
