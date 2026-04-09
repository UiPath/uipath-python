"""Mock runtime delegate that manages mocking execution context."""

from __future__ import annotations

import json
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
    ToolSimulation,
)

logger = logging.getLogger(__name__)


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
        with open(simulation_path, "r", encoding="utf-8") as f:
            simulation_data = json.load(f)

        # Check if simulation is enabled
        if not simulation_data.get("enabled", True):
            return None

        # Extract tools to simulate
        tools_to_simulate = [
            ToolSimulation(name=tool["name"])
            for tool in simulation_data.get("toolsToSimulate", [])
        ]

        if not tools_to_simulate:
            return None

        # Create LLM mocking strategy
        mocking_strategy = LLMMockingStrategy(
            type=MockingStrategyType.LLM,
            prompt=simulation_data.get("instructions", ""),
            tools_to_simulate=tools_to_simulate,
        )

        # Create MockingContext for debugging
        mocking_context = MockingContext(
            strategy=mocking_strategy,
            name="debug-simulation",
            inputs={},
            agent_model=agent_model,
        )

        logger.info(f"Loaded simulation config for {len(tools_to_simulate)} tool(s)")
        return mocking_context

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
        agent_model: str | None = None,
    ):
        self.delegate = delegate
        self._mocking_context = mocking_context or load_simulation_config(
            agent_model=agent_model
        )
        # If mocking_context was passed without agent_model, inject it
        if (
            self._mocking_context
            and not self._mocking_context.agent_model
            and agent_model
        ):
            self._mocking_context = self._mocking_context.model_copy(
                update={"agent_model": agent_model}
            )
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
