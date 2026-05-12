"""Mock runtime delegate that manages mocking execution context."""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

from uipath.runtime import (
    UiPathExecuteOptions,
    UiPathRuntimeProtocol,
    UiPathRuntimeResult,
)
from uipath.runtime.schema import UiPathRuntimeSchema

from .._execution_context import (
    ExecutionSpanCollector,
    eval_set_run_id_context,
    execution_id_context,
    span_collector_context,
)
from ._mock_context import mocker_context, mocking_context
from ._mocker_factory import MockerFactory
from ._types import (
    LLMMockingStrategy,
    MockingContext,
    MockingStrategyType,
    ModelSettings,
    SimulationConfig,
)

logger = logging.getLogger(__name__)


def build_mocking_context(
    config: SimulationConfig, agent_model: str | None = None
) -> MockingContext | None:
    """Build a MockingContext from a validated SimulationConfig.

    Args:
        config: Validated simulation config.
        agent_model: Optional agent model name to use as fallback.

    Returns:
        MockingContext if enabled and tools are specified, None otherwise.
    """
    if not config.enabled or not config.tools_to_simulate:
        return None

    model = (
        ModelSettings(model=config.model)
        if config.model
        else ModelSettings(model=agent_model)
        if agent_model
        else None
    )

    mocking_strategy = LLMMockingStrategy(
        type=MockingStrategyType.LLM,
        prompt=config.instructions,
        tools_to_simulate=config.tools_to_simulate,
        model=model,
    )

    logger.debug(
        f"Loaded simulation config for {len(config.tools_to_simulate)} tool(s)"
    )
    return MockingContext(
        strategy=mocking_strategy,
        name="debug-simulation",
        inputs={},
    )


def build_mocking_context_from_dict(
    simulation_data: dict[str, Any], agent_model: str | None = None
) -> MockingContext | None:
    """Build a MockingContext from a simulation config dictionary.

    Deprecated: prefer build_mocking_context with a validated SimulationConfig.

    Args:
        simulation_data: Parsed simulation config (same schema as simulation.json).
        agent_model: Optional agent model name to use as fallback.

    Returns:
        MockingContext if valid and enabled, None otherwise.
    """
    config = SimulationConfig.model_validate(simulation_data)
    return build_mocking_context(config, agent_model)


def load_simulation_config(agent_model: str | None = None) -> MockingContext | None:
    """Load simulation.json from current directory and convert to MockingContext.

    Returns:
        MockingContext with LLM mocking strategy if simulation.json exists and is valid,
        None otherwise.
    """
    simulation_path = Path.cwd() / "simulation.json"

    if not simulation_path.exists():
        return None

    try:
        config = SimulationConfig.model_validate_json(
            simulation_path.read_text(encoding="utf-8")
        )
        return build_mocking_context(config, agent_model)

    except Exception as e:
        logger.warning(f"Failed to load simulation.json: {e}")
        return None


def set_execution_context(
    context: MockingContext | None,
    span_collector: ExecutionSpanCollector,
    execution_id: str | None = None,
    eval_set_run_id: str | None = None,
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
    eval_set_run_id_context.set(eval_set_run_id)


def clear_execution_context() -> None:
    """Clear the execution context after evaluation completes."""
    mocking_context.set(None)
    mocker_context.set(None)
    span_collector_context.set(None)
    execution_id_context.set(None)


class UiPathMockRuntime:
    """Runtime delegate that manages mocking execution context.

    Wraps an inner runtime and automatically sets/clears the mocking
    execution context around each execute() and stream() call.

    When no mocking_context is provided, falls back to loading
    simulation.json from the current directory.
    """

    def __init__(
        self,
        delegate: UiPathRuntimeProtocol,
        mocking_context: MockingContext | None = None,
        span_collector: ExecutionSpanCollector | None = None,
        execution_id: str | None = None,
        eval_set_run_id: str | None = None,
    ):
        self.delegate = delegate
        self._mocking_context = mocking_context or load_simulation_config()
        self._span_collector = span_collector or ExecutionSpanCollector()
        self._execution_id = execution_id or str(uuid.uuid4())
        self._eval_set_run_id = eval_set_run_id

    async def execute(
        self,
        input: dict[str, Any] | None = None,
        options: UiPathExecuteOptions | None = None,
    ) -> UiPathRuntimeResult:
        """Execute with mocking context set around the delegate call."""
        if not self._mocking_context:
            return await self.delegate.execute(input, options)

        set_execution_context(
            self._mocking_context,
            self._span_collector,
            self._execution_id,
            self._eval_set_run_id,
        )
        try:
            return await self.delegate.execute(input, options)
        finally:
            clear_execution_context()

    async def stream(
        self,
        input: dict[str, Any] | None = None,
        options: Any | None = None,
    ) -> AsyncGenerator[Any, None]:
        """Stream with mocking context set around the delegate call."""
        if not self._mocking_context:
            async for event in self.delegate.stream(input, options):
                yield event
        else:
            set_execution_context(
                self._mocking_context,
                self._span_collector,
                self._execution_id,
                self._eval_set_run_id,
            )
            try:
                async for event in self.delegate.stream(input, options):
                    yield event
            finally:
                clear_execution_context()

    async def get_schema(self) -> UiPathRuntimeSchema:
        """Pass through to delegate."""
        return await self.delegate.get_schema()

    async def dispose(self) -> None:
        """No-op; callers manage delegate disposal."""
        pass
