"""Tests for UiPathEvalRuntime metadata loading functionality.

This module tests:
- _get_agent_model() - cached agent model retrieval
- get_schema() - cached schema retrieval
"""

import uuid
from typing import Any, AsyncGenerator

import pytest
from uipath.core.tracing import UiPathTraceManager
from uipath.runtime import (
    UiPathExecuteOptions,
    UiPathRuntimeEvent,
    UiPathRuntimeFactorySettings,
    UiPathRuntimeProtocol,
    UiPathRuntimeResult,
    UiPathRuntimeStatus,
    UiPathRuntimeStorageProtocol,
    UiPathStreamOptions,
)
from uipath.runtime.schema import UiPathRuntimeSchema

from uipath._cli._evals._runtime import (
    UiPathEvalContext,
    UiPathEvalRuntime,
)
from uipath._cli.cli_eval import (
    _get_agent_model,
)
from uipath._events._event_bus import EventBus


class MockRuntimeSchema(UiPathRuntimeSchema):
    """Mock schema for testing."""

    def __init__(self):
        super().__init__(
            filePath="test.py",
            uniqueId="test",
            type="workflow",
            input={"type": "object", "properties": {}},
            output={"type": "object", "properties": {}},
        )


class BaseTestRuntime:
    """Base test runtime without agent model support."""

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
        return MockRuntimeSchema()

    async def dispose(self) -> None:
        pass


class WrapperRuntime(BaseTestRuntime):
    """Test runtime that wraps another runtime (like UiPathResumableRuntime)."""

    def __init__(self, delegate: Any):
        self.delegate = delegate

    async def get_schema(self) -> UiPathRuntimeSchema:
        return await self.delegate.get_schema()


class PrivateDelegateRuntime(BaseTestRuntime):
    """Test runtime with private _delegate attribute."""

    def __init__(self, delegate: Any):
        self._delegate = delegate

    async def get_schema(self) -> UiPathRuntimeSchema:
        return await self._delegate.get_schema()


class MockFactory:
    """Mock factory for creating test runtimes."""

    def __init__(self, runtime_creator):
        self.runtime_creator = runtime_creator
        self.new_runtime_call_count = 0

    def discover_entrypoints(self) -> list[str]:
        return ["test"]

    async def get_storage(self) -> UiPathRuntimeStorageProtocol | None:
        return None

    async def get_settings(self) -> UiPathRuntimeFactorySettings | None:
        return None

    async def new_runtime(
        self, entrypoint: str, runtime_id: str, **kwargs
    ) -> UiPathRuntimeProtocol:
        self.new_runtime_call_count += 1
        return await self.runtime_creator()

    async def dispose(self) -> None:
        pass


class TestGetAgentModel:
    """Tests for _get_agent_model function."""

    @pytest.mark.asyncio
    async def test_returns_agent_model(self):
        """Test that _get_agent_model returns the correct model from schema."""
        schema = MockRuntimeSchema()
        schema.metadata = {"settings": {"model": "gpt-4o-2024-11-20"}}

        model = await _get_agent_model(schema)
        assert model == "gpt-4o-2024-11-20"

    @pytest.mark.asyncio
    async def test_returns_none_when_no_model(self):
        """Test that _get_agent_model returns None when runtime has no model."""
        schema = MockRuntimeSchema()

        model = await _get_agent_model(schema)
        assert model is None

    @pytest.mark.asyncio
    async def test_returns_model_consistently(self):
        """Test that _get_agent_model returns consistent results."""
        schema = MockRuntimeSchema()
        schema.metadata = {"settings": {"model": "consistent-model"}}

        # Multiple calls should return the same value
        model1 = await _get_agent_model(schema)
        model2 = await _get_agent_model(schema)

        assert model1 == model2 == "consistent-model"


class TestGetSchema:
    """Tests for get_schema method."""

    @pytest.mark.asyncio
    async def test_returns_schema(self):
        """Test that get_schema returns the schema from context."""
        schema = MockRuntimeSchema()
        context = UiPathEvalContext()
        context.execution_id = str(uuid.uuid4())
        context.evaluation_set = None  # type: ignore
        context.runtime_schema = schema
        context.evaluators = []

        async def create_runtime():
            return BaseTestRuntime()

        factory = MockFactory(create_runtime)
        event_bus = EventBus()
        trace_manager = UiPathTraceManager()
        eval_runtime = UiPathEvalRuntime(
            context,
            factory,
            trace_manager,
            event_bus,
        )

        retrieved_schema = await eval_runtime.get_schema()
        assert retrieved_schema is not None
        assert retrieved_schema.file_path == "test.py"

    @pytest.mark.asyncio
    async def test_returns_schema_consistently(self):
        """Test that get_schema returns the same schema from context."""
        schema = MockRuntimeSchema()
        context = UiPathEvalContext()
        context.execution_id = str(uuid.uuid4())
        context.evaluation_set = None  # type: ignore
        context.runtime_schema = schema
        context.evaluators = []

        async def create_runtime():
            return BaseTestRuntime()

        factory = MockFactory(create_runtime)
        event_bus = EventBus()
        trace_manager = UiPathTraceManager()
        eval_runtime = UiPathEvalRuntime(
            context,
            factory,
            trace_manager,
            event_bus,
        )

        # Multiple calls should return the same schema from context
        schema1 = await eval_runtime.get_schema()
        schema2 = await eval_runtime.get_schema()

        # Should be the same object
        assert schema1 is schema2
        assert schema1.file_path == schema2.file_path == "test.py"
