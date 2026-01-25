"""Tests for UiPathEvalRuntime suspend/resume event publishing.

This module tests:
- Normal flow: CREATE_EVAL_RUN event is published, eval_run_id saved to disk
- Resume flow: CREATE_EVAL_RUN event is NOT published, eval_run_id loaded from disk
- UPDATE_EVAL_RUN works correctly after evaluators complete
- Ensures no duplicate eval run entries in StudioWeb
"""

from pathlib import Path
from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock

import pytest
from uipath.core.tracing import UiPathTraceManager
from uipath.runtime import (
    UiPathExecuteOptions,
    UiPathRuntimeEvent,
    UiPathRuntimeProtocol,
    UiPathRuntimeResult,
    UiPathRuntimeStatus,
    UiPathStreamOptions,
)
from uipath.runtime.schema import UiPathRuntimeSchema

from uipath._cli._evals._evaluate import evaluate
from uipath._cli._evals._runtime import UiPathEvalContext
from uipath._events._event_bus import EventBus
from uipath._events._events import EvaluationEvents


class MockRuntimeSchema(UiPathRuntimeSchema):
    """Mock schema for testing."""

    def __init__(self):
        super().__init__(
            filePath="test.py",
            uniqueId="test",
            type="agent",
            input={"type": "object", "properties": {}},
            output={"type": "object", "properties": {}},
        )


class SuspendingRuntime:
    """Test runtime that returns SUSPENDED status."""

    async def execute(
        self,
        input: dict[str, Any] | None = None,
        options: UiPathExecuteOptions | None = None,
    ) -> UiPathRuntimeResult:
        # Simulate an agent that suspends
        # Returning SUSPENDED status is sufficient for our test
        return UiPathRuntimeResult(
            output={},
            status=UiPathRuntimeStatus.SUSPENDED,
        )

    async def stream(
        self,
        input: dict[str, Any] | None = None,
        options: UiPathStreamOptions | None = None,
    ) -> AsyncGenerator[UiPathRuntimeEvent, None]:
        yield UiPathRuntimeResult(
            output={},
            status=UiPathRuntimeStatus.SUSPENDED,
        )

    async def get_schema(self) -> UiPathRuntimeSchema:
        return MockRuntimeSchema()

    async def dispose(self) -> None:
        pass


class SuccessfulRuntime:
    """Test runtime that returns SUCCESSFUL status."""

    async def execute(
        self,
        input: dict[str, Any] | None = None,
        options: UiPathExecuteOptions | None = None,
    ) -> UiPathRuntimeResult:
        return UiPathRuntimeResult(
            output={"result": "success"},
            status=UiPathRuntimeStatus.SUCCESSFUL,
        )

    async def stream(
        self,
        input: dict[str, Any] | None = None,
        options: UiPathStreamOptions | None = None,
    ) -> AsyncGenerator[UiPathRuntimeEvent, None]:
        yield UiPathRuntimeResult(
            output={"result": "success"},
            status=UiPathRuntimeStatus.SUCCESSFUL,
        )

    async def get_schema(self) -> UiPathRuntimeSchema:
        return MockRuntimeSchema()

    async def dispose(self) -> None:
        pass


class MockFactory:
    """Mock factory for creating test runtimes."""

    def __init__(self, runtime_creator):
        self.runtime_creator = runtime_creator

    def discover_entrypoints(self) -> list[str]:
        return ["test"]

    async def discover_runtimes(self) -> list[UiPathRuntimeProtocol]:
        return [await self.runtime_creator()]

    async def new_runtime(
        self, entrypoint: str, runtime_id: str, **kwargs
    ) -> UiPathRuntimeProtocol:
        return await self.runtime_creator()

    async def dispose(self) -> None:
        pass


@pytest.fixture
def context():
    """Create eval context."""
    context = UiPathEvalContext()
    context.eval_set = str(
        Path(__file__).parent / "evals" / "eval-sets" / "default.json"
    )
    return context


@pytest.fixture
def event_bus():
    """Create event bus with mocked publish method."""
    bus = EventBus()
    bus.publish = AsyncMock()  # type: ignore[method-assign]
    return bus


@pytest.fixture
def trace_manager():
    """Create trace manager."""
    return UiPathTraceManager()


class TestNormalFlowCreateEvalRun:
    """Tests for normal execution flow - CREATE_EVAL_RUN should be published."""

    async def test_publishes_create_eval_run_on_successful_execution(
        self, context, event_bus, trace_manager
    ):
        """Test that CREATE_EVAL_RUN is published during normal successful execution."""

        # Arrange
        async def create_runtime():
            return SuccessfulRuntime()

        factory = MockFactory(create_runtime)

        # Act
        await evaluate(factory, trace_manager, context, event_bus)

        # Assert
        # Check that CREATE_EVAL_RUN was published
        create_calls = [
            call
            for call in event_bus.publish.call_args_list
            if call[0][0] == EvaluationEvents.CREATE_EVAL_RUN
        ]
        assert len(create_calls) > 0, (
            "CREATE_EVAL_RUN should be published in normal flow"
        )

    async def test_publishes_create_eval_run_on_suspend(
        self, context, event_bus, trace_manager
    ):
        """Test that CREATE_EVAL_RUN is published when agent suspends."""

        # Arrange
        async def create_runtime():
            return SuspendingRuntime()

        factory = MockFactory(create_runtime)

        # Act
        await evaluate(factory, trace_manager, context, event_bus)

        # Assert
        # Check that CREATE_EVAL_RUN was published
        create_calls = [
            call
            for call in event_bus.publish.call_args_list
            if call[0][0] == EvaluationEvents.CREATE_EVAL_RUN
        ]
        assert len(create_calls) > 0, (
            "CREATE_EVAL_RUN should be published on suspend (initial execution)"
        )


class TestResumeFlowSkipsCreateEvalRun:
    """Tests for resume flow - CREATE_EVAL_RUN should NOT be published, eval_run_id loaded from disk."""

    async def test_skips_create_eval_run_on_resume(
        self, context, event_bus, trace_manager
    ):
        """Test that CREATE_EVAL_RUN is NOT published when resuming from checkpoint.

        During resume, the eval_run_id mapping is loaded from the persisted file
        (__uipath/eval_run_ids.json) instead of making a new CREATE_EVAL_RUN API call.
        This prevents duplicate entries in StudioWeb.
        """
        # Arrange
        context.resume = True  # Set resume flag

        async def create_runtime():
            return SuccessfulRuntime()

        factory = MockFactory(create_runtime)

        # Act
        await evaluate(factory, trace_manager, context, event_bus)

        # Assert
        # Check that CREATE_EVAL_RUN was NOT published
        create_calls = [
            call
            for call in event_bus.publish.call_args_list
            if call[0][0] == EvaluationEvents.CREATE_EVAL_RUN
        ]
        assert len(create_calls) == 0, (
            "CREATE_EVAL_RUN should NOT be published on resume (loaded from disk instead)"
        )

    async def test_publishes_update_eval_run_on_resume(
        self, context, event_bus, trace_manager
    ):
        """Test that UPDATE_EVAL_RUN is still published when resuming."""
        # Arrange
        context.resume = True  # Set resume flag

        async def create_runtime():
            return SuccessfulRuntime()

        factory = MockFactory(create_runtime)

        # Act
        await evaluate(factory, trace_manager, context, event_bus)

        # Assert
        # Check that UPDATE_EVAL_RUN was published
        update_calls = [
            call
            for call in event_bus.publish.call_args_list
            if call[0][0] == EvaluationEvents.UPDATE_EVAL_RUN
        ]
        assert len(update_calls) > 0, (
            "UPDATE_EVAL_RUN should still be published on resume"
        )

    async def test_resume_flag_false_by_default(self, context):
        """Test that resume flag is False by default in context."""
        assert context.resume is False, "resume should default to False"

    async def test_no_duplicate_entries_on_resume(
        self, context, event_bus, trace_manager
    ):
        """Test that resuming doesn't create duplicate entries (integration test concept).

        This test verifies that when resume=True:
        1. CREATE_EVAL_RUN is NOT called (prevents duplicate backend entries)
        2. Only UPDATE_EVAL_RUN is called (updates existing entry)

        The eval_run_id mapping is loaded from persisted state on disk.
        """
        # Arrange
        context.resume = True

        async def create_runtime():
            return SuccessfulRuntime()

        factory = MockFactory(create_runtime)

        # Act
        await evaluate(factory, trace_manager, context, event_bus)

        # Assert
        create_calls = [
            call
            for call in event_bus.publish.call_args_list
            if call[0][0] == EvaluationEvents.CREATE_EVAL_RUN
        ]
        update_calls = [
            call
            for call in event_bus.publish.call_args_list
            if call[0][0] == EvaluationEvents.UPDATE_EVAL_RUN
        ]

        assert len(create_calls) == 0, "Should NOT create new entry on resume"
        assert len(update_calls) > 0, "Should update existing entry on resume"


class TestSuspendResumeLifecycle:
    """Tests for complete suspend/resume lifecycle."""

    async def test_suspend_then_resume_lifecycle(self, context, trace_manager):
        """Test complete lifecycle: suspend (creates entry) then resume (updates entry)."""
        # Phase 1: Suspend
        event_bus_suspend = EventBus()
        event_bus_suspend.publish = AsyncMock()  # type: ignore[method-assign]

        async def create_suspending_runtime():
            return SuspendingRuntime()

        factory_suspend = MockFactory(create_suspending_runtime)

        await evaluate(factory_suspend, trace_manager, context, event_bus_suspend)

        # Assert suspend phase
        suspend_create_calls = [
            call
            for call in event_bus_suspend.publish.call_args_list
            if call[0][0] == EvaluationEvents.CREATE_EVAL_RUN
        ]
        suspend_update_calls = [
            call
            for call in event_bus_suspend.publish.call_args_list
            if call[0][0] == EvaluationEvents.UPDATE_EVAL_RUN
        ]

        assert len(suspend_create_calls) > 0, "Suspend phase should CREATE entry"
        assert len(suspend_update_calls) == 0, (
            "Suspend phase should NOT UPDATE - evalRun stays IN_PROGRESS until resume"
        )

        # Phase 2: Resume
        context.resume = True
        event_bus_resume = EventBus()
        event_bus_resume.publish = AsyncMock()  # type: ignore[method-assign]

        async def create_successful_runtime():
            return SuccessfulRuntime()

        factory_resume = MockFactory(create_successful_runtime)

        await evaluate(factory_resume, trace_manager, context, event_bus_resume)

        # Assert resume phase
        resume_create_calls = [
            call
            for call in event_bus_resume.publish.call_args_list
            if call[0][0] == EvaluationEvents.CREATE_EVAL_RUN
        ]
        resume_update_calls = [
            call
            for call in event_bus_resume.publish.call_args_list
            if call[0][0] == EvaluationEvents.UPDATE_EVAL_RUN
        ]

        assert len(resume_create_calls) == 0, "Resume phase should NOT CREATE new entry"
        assert len(resume_update_calls) > 0, "Resume phase should UPDATE existing entry"
