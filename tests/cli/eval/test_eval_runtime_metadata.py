"""Tests for UiPathEvalRuntime metadata loading functionality.

This module tests:
- _get_agent_model() - reading agent model from schema.metadata
- get_schema() - schema retrieval
"""

from pathlib import Path
from typing import Any, AsyncGenerator

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

from uipath._cli._evals._runtime import (
    UiPathEvalContext,
    UiPathEvalRuntime,
)
from uipath._events._event_bus import EventBus


class MockRuntimeSchema(UiPathRuntimeSchema):
    """Mock schema for testing."""

    def __init__(self, metadata: dict[str, Any] | None = None):
        super().__init__(
            filePath="test.py",
            uniqueId="test",
            type="workflow",
            input={"type": "object", "properties": {}},
            output={"type": "object", "properties": {}},
            metadata=metadata,
        )


class BaseTestRuntime:
    """Base test runtime with configurable metadata."""

    def __init__(self, metadata: dict[str, Any] | None = None):
        self._metadata = metadata

    async def execute(
        self,
        input: dict[str, Any] | None = None,
        options: UiPathExecuteOptions | None = None,
    ) -> UiPathRuntimeResult:
        return UiPathRuntimeResult(
            output={},
            status=UiPathRuntimeStatus.SUCCESSFUL,
        )

    async def stream(
        self,
        input: dict[str, Any] | None = None,
        options: UiPathStreamOptions | None = None,
    ) -> AsyncGenerator[UiPathRuntimeEvent, None]:
        yield UiPathRuntimeResult(
            output={},
            status=UiPathRuntimeStatus.SUCCESSFUL,
        )

    async def get_schema(self) -> UiPathRuntimeSchema:
        return MockRuntimeSchema(metadata=self._metadata)

    async def dispose(self) -> None:
        pass


class MockFactory:
    """Mock factory for creating test runtimes."""

    def __init__(self, runtime_creator):
        self.runtime_creator = runtime_creator
        self.new_runtime_call_count = 0

    def discover_entrypoints(self) -> list[str]:
        return ["test"]

    async def discover_runtimes(self) -> list[UiPathRuntimeProtocol]:
        return [await self.runtime_creator()]

    async def new_runtime(
        self, entrypoint: str, runtime_id: str, **kwargs
    ) -> UiPathRuntimeProtocol:
        self.new_runtime_call_count += 1
        return await self.runtime_creator()

    async def dispose(self) -> None:
        pass


class TestGetAgentModel:
    """Tests for _get_agent_model method reading from schema.metadata."""

    @pytest.fixture
    def context(self):
        """Create eval context."""
        context = UiPathEvalContext()
        context.eval_set = str(
            Path(__file__).parent / "evals" / "eval-sets" / "default.json"
        )
        return context

    async def test_returns_agent_model_from_metadata(self, context):
        """Test that _get_agent_model reads from schema.metadata."""
        metadata = {"settings": {"model": "gpt-4o-2024-11-20"}}

        async def create_runtime():
            return BaseTestRuntime(metadata=metadata)

        factory = MockFactory(create_runtime)
        event_bus = EventBus()
        trace_manager = UiPathTraceManager()
        eval_runtime = UiPathEvalRuntime(context, factory, trace_manager, event_bus)

        runtime = await create_runtime()
        model = await eval_runtime._get_agent_model(runtime)
        assert model == "gpt-4o-2024-11-20"

    async def test_returns_none_when_no_metadata(self, context):
        """Test that _get_agent_model returns None when metadata is missing."""

        async def create_runtime():
            return BaseTestRuntime(metadata=None)

        factory = MockFactory(create_runtime)
        event_bus = EventBus()
        trace_manager = UiPathTraceManager()
        eval_runtime = UiPathEvalRuntime(context, factory, trace_manager, event_bus)

        runtime = await create_runtime()
        model = await eval_runtime._get_agent_model(runtime)
        assert model is None

    async def test_returns_none_when_no_settings_in_metadata(self, context):
        """Test that _get_agent_model returns None when settings key is missing."""
        metadata = {"other": "data"}

        async def create_runtime():
            return BaseTestRuntime(metadata=metadata)

        factory = MockFactory(create_runtime)
        event_bus = EventBus()
        trace_manager = UiPathTraceManager()
        eval_runtime = UiPathEvalRuntime(context, factory, trace_manager, event_bus)

        runtime = await create_runtime()
        model = await eval_runtime._get_agent_model(runtime)
        assert model is None

    async def test_returns_none_when_no_model_in_settings(self, context):
        """Test that _get_agent_model returns None when model key is missing."""
        metadata = {"settings": {"temperature": 0.7}}

        async def create_runtime():
            return BaseTestRuntime(metadata=metadata)

        factory = MockFactory(create_runtime)
        event_bus = EventBus()
        trace_manager = UiPathTraceManager()
        eval_runtime = UiPathEvalRuntime(context, factory, trace_manager, event_bus)

        runtime = await create_runtime()
        model = await eval_runtime._get_agent_model(runtime)
        assert model is None

    async def test_returns_model_consistently(self, context):
        """Test that _get_agent_model returns consistent results."""
        metadata = {"settings": {"model": "consistent-model"}}

        async def create_runtime():
            return BaseTestRuntime(metadata=metadata)

        factory = MockFactory(create_runtime)
        event_bus = EventBus()
        trace_manager = UiPathTraceManager()
        eval_runtime = UiPathEvalRuntime(context, factory, trace_manager, event_bus)

        runtime = await create_runtime()

        # Multiple calls should return the same value
        model1 = await eval_runtime._get_agent_model(runtime)
        model2 = await eval_runtime._get_agent_model(runtime)

        assert model1 == model2 == "consistent-model"

    async def test_handles_exception_gracefully(self, context):
        """Test that _get_agent_model returns None on exception."""

        async def create_runtime():
            # Runtime that raises exception when getting schema
            class BadRuntime(BaseTestRuntime):
                async def get_schema(self):
                    raise RuntimeError("Schema error")

            return BadRuntime()

        factory = MockFactory(create_runtime)
        event_bus = EventBus()
        trace_manager = UiPathTraceManager()
        eval_runtime = UiPathEvalRuntime(context, factory, trace_manager, event_bus)

        bad_runtime = await create_runtime()
        model = await eval_runtime._get_agent_model(bad_runtime)
        assert model is None


class TestGetSchema:
    """Tests for get_schema method."""

    @pytest.fixture
    def context(self):
        """Create eval context."""
        context = UiPathEvalContext()
        context.eval_set = str(
            Path(__file__).parent / "evals" / "eval-sets" / "default.json"
        )
        return context

    async def test_returns_schema(self, context):
        """Test that get_schema returns the schema."""
        metadata = {"settings": {"model": "test-model"}}

        async def create_runtime():
            return BaseTestRuntime(metadata=metadata)

        factory = MockFactory(create_runtime)
        event_bus = EventBus()
        trace_manager = UiPathTraceManager()
        eval_runtime = UiPathEvalRuntime(context, factory, trace_manager, event_bus)

        runtime = await create_runtime()
        schema = await eval_runtime.get_schema(runtime)
        assert schema is not None
        assert schema.file_path == "test.py"

    async def test_returns_schema_consistently(self, context):
        """Test that get_schema returns consistent results."""
        metadata = {"settings": {"model": "test-model"}}

        async def create_runtime():
            return BaseTestRuntime(metadata=metadata)

        factory = MockFactory(create_runtime)
        event_bus = EventBus()
        trace_manager = UiPathTraceManager()
        eval_runtime = UiPathEvalRuntime(context, factory, trace_manager, event_bus)

        runtime = await create_runtime()

        # Multiple calls should return equivalent values
        schema1 = await eval_runtime.get_schema(runtime)
        schema2 = await eval_runtime.get_schema(runtime)

        # Should have the same properties
        assert schema1.file_path == schema2.file_path == "test.py"

    async def test_schema_and_model_work_with_same_runtime(self, context):
        """Test that get_schema and _get_agent_model work with the same runtime."""
        metadata = {"settings": {"model": "shared-model"}}

        async def create_runtime():
            return BaseTestRuntime(metadata=metadata)

        factory = MockFactory(create_runtime)
        event_bus = EventBus()
        trace_manager = UiPathTraceManager()
        eval_runtime = UiPathEvalRuntime(context, factory, trace_manager, event_bus)

        runtime = await create_runtime()

        # Call both methods with the same runtime
        schema = await eval_runtime.get_schema(runtime)
        model = await eval_runtime._get_agent_model(runtime)

        # Both should work correctly
        assert schema is not None
        assert schema.file_path == "test.py"
        assert model == "shared-model"
