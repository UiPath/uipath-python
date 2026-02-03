"""Tests for UiPathEvalRuntime metadata loading functionality.

This module tests:
- _ensure_metadata_loaded() - single runtime creation for both schema and agent model
- _get_agent_model() - cached agent model retrieval
- get_schema() - cached schema retrieval
- _find_agent_model_in_runtime() - recursive delegate traversal
- LLMAgentRuntimeProtocol - protocol implementation detection
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
    LLMAgentRuntimeProtocol,
    UiPathEvalContext,
    UiPathEvalRuntime,
)
from uipath._cli.cli_eval import (
    _find_agent_model_in_runtime,
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


class AgentModelRuntime(BaseTestRuntime):
    """Test runtime that implements LLMAgentRuntimeProtocol."""

    def __init__(self, model: str | None = "gpt-4o-2024-11-20"):
        self._model = model

    def get_agent_model(self) -> str | None:
        return self._model


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


class TestLLMAgentRuntimeProtocol:
    """Tests for LLMAgentRuntimeProtocol detection."""

    def test_protocol_detects_implementing_class(self):
        """Test that protocol correctly identifies implementing classes."""
        runtime = AgentModelRuntime("gpt-4")
        assert isinstance(runtime, LLMAgentRuntimeProtocol)

    def test_protocol_rejects_non_implementing_class(self):
        """Test that protocol correctly rejects non-implementing classes."""
        runtime = BaseTestRuntime()
        assert not isinstance(runtime, LLMAgentRuntimeProtocol)

    def test_protocol_rejects_wrapper_without_method(self):
        """Test that wrapper without get_agent_model is not detected."""
        inner = AgentModelRuntime("gpt-4")
        wrapper = WrapperRuntime(inner)
        assert not isinstance(wrapper, LLMAgentRuntimeProtocol)


class TestFindAgentModelInRuntime:
    """Tests for _find_agent_model_in_runtime recursive search."""

    def test_finds_model_in_direct_runtime(self):
        """Test finding agent model directly on runtime."""
        runtime = AgentModelRuntime("gpt-4o")
        result = _find_agent_model_in_runtime(runtime)
        assert result == "gpt-4o"

    def test_finds_model_in_wrapped_runtime(self):
        """Test finding agent model through wrapper's delegate."""
        inner = AgentModelRuntime("claude-3")
        wrapper = WrapperRuntime(inner)
        result = _find_agent_model_in_runtime(wrapper)
        assert result == "claude-3"

    def test_finds_model_in_deeply_wrapped_runtime(self):
        """Test finding agent model through multiple wrapper layers."""
        inner = AgentModelRuntime("gpt-4-turbo")
        wrapper1 = WrapperRuntime(inner)
        wrapper2 = WrapperRuntime(wrapper1)
        result = _find_agent_model_in_runtime(wrapper2)
        assert result == "gpt-4-turbo"

    def test_finds_model_via_private_delegate(self):
        """Test finding agent model through _delegate attribute."""
        inner = AgentModelRuntime("gemini-pro")
        wrapper = PrivateDelegateRuntime(inner)
        result = _find_agent_model_in_runtime(wrapper)
        assert result == "gemini-pro"

    def test_returns_none_when_no_model(self):
        """Test returns None when no runtime implements the protocol."""
        runtime = BaseTestRuntime()
        result = _find_agent_model_in_runtime(runtime)
        assert result is None

    def test_returns_none_for_none_model(self):
        """Test returns None when runtime returns None for model."""
        runtime = AgentModelRuntime(None)
        result = _find_agent_model_in_runtime(runtime)
        assert result is None


class TestGetAgentModel:
    """Tests for _get_agent_model function."""

    @pytest.mark.asyncio
    async def test_returns_agent_model(self):
        """Test that _get_agent_model returns the correct model from schema."""
        runtime = AgentModelRuntime("gpt-4o-2024-11-20")
        schema = MockRuntimeSchema()
        schema.metadata = {"settings": {"model": "gpt-4o-2024-11-20"}}

        model = await _get_agent_model(runtime, schema)
        assert model == "gpt-4o-2024-11-20"

    @pytest.mark.asyncio
    async def test_returns_none_when_no_model(self):
        """Test that _get_agent_model returns None when runtime has no model."""
        runtime = BaseTestRuntime()
        schema = MockRuntimeSchema()

        model = await _get_agent_model(runtime, schema)
        assert model is None

    @pytest.mark.asyncio
    async def test_returns_model_consistently(self):
        """Test that _get_agent_model returns consistent results."""
        runtime = AgentModelRuntime("consistent-model")
        schema = MockRuntimeSchema()
        schema.metadata = {"settings": {"model": "consistent-model"}}

        # Multiple calls should return the same value
        model1 = await _get_agent_model(runtime, schema)
        model2 = await _get_agent_model(runtime, schema)

        assert model1 == model2 == "consistent-model"

    @pytest.mark.asyncio
    async def test_handles_exception_gracefully(self, monkeypatch):
        """Test that _get_agent_model returns None when _find_agent_model_in_runtime raises exception."""
        runtime = BaseTestRuntime()
        schema = MockRuntimeSchema()

        # Mock _find_agent_model_in_runtime to raise an exception
        def mock_find_agent_model_error(r):
            raise RuntimeError("Unexpected error during model lookup")

        monkeypatch.setattr(
            "uipath._cli.cli_eval._find_agent_model_in_runtime",
            mock_find_agent_model_error,
        )

        model = await _get_agent_model(runtime, schema)
        assert model is None


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


class TestWrappedRuntimeModelResolution:
    """Tests for model resolution through realistic wrapper chains."""

    def test_resolves_model_through_resumable_telemetry_chain(self):
        """Test model resolution through ResumableRuntime -> TelemetryWrapper -> BaseRuntime chain.

        This mimics the real wrapper chain:
        UiPathResumableRuntime -> TelemetryRuntimeWrapper -> AgentsLangGraphRuntime
        """
        # Base runtime with model
        base_runtime = AgentModelRuntime("gpt-4o-from-agent-json")

        # Simulate TelemetryRuntimeWrapper
        telemetry_wrapper = WrapperRuntime(base_runtime)

        # Simulate UiPathResumableRuntime
        resumable_runtime = WrapperRuntime(telemetry_wrapper)

        model = _find_agent_model_in_runtime(resumable_runtime)
        assert model == "gpt-4o-from-agent-json"
