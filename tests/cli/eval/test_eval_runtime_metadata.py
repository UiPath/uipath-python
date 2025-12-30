"""Tests for UiPathEvalRuntime metadata loading functionality.

This module tests:
- _ensure_metadata_loaded() - single runtime creation for both schema and agent model
- _get_agent_model() - cached agent model retrieval
- get_schema() - cached schema retrieval
- _find_agent_model_in_runtime() - recursive delegate traversal
- LLMAgentRuntimeProtocol - protocol implementation detection
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
    LLMAgentRuntimeProtocol,
    UiPathEvalContext,
    UiPathEvalRuntime,
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

    async def discover_runtimes(self) -> list[UiPathRuntimeProtocol]:
        return [await self.runtime_creator()]

    async def new_runtime(
        self, entrypoint: str, runtime_id: str
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

    @pytest.fixture
    def eval_runtime(self):
        """Create an eval runtime for testing."""
        context = UiPathEvalContext()
        context.eval_set = str(
            Path(__file__).parent / "evals" / "eval-sets" / "default.json"
        )
        event_bus = EventBus()
        trace_manager = UiPathTraceManager()

        async def create_runtime():
            return BaseTestRuntime()

        factory = MockFactory(create_runtime)
        return UiPathEvalRuntime(context, factory, trace_manager, event_bus)

    def test_finds_model_in_direct_runtime(self, eval_runtime):
        """Test finding agent model directly on runtime."""
        runtime = AgentModelRuntime("gpt-4o")
        result = eval_runtime._find_agent_model_in_runtime(runtime)
        assert result == "gpt-4o"

    def test_finds_model_in_wrapped_runtime(self, eval_runtime):
        """Test finding agent model through wrapper's delegate."""
        inner = AgentModelRuntime("claude-3")
        wrapper = WrapperRuntime(inner)
        result = eval_runtime._find_agent_model_in_runtime(wrapper)
        assert result == "claude-3"

    def test_finds_model_in_deeply_wrapped_runtime(self, eval_runtime):
        """Test finding agent model through multiple wrapper layers."""
        inner = AgentModelRuntime("gpt-4-turbo")
        wrapper1 = WrapperRuntime(inner)
        wrapper2 = WrapperRuntime(wrapper1)
        result = eval_runtime._find_agent_model_in_runtime(wrapper2)
        assert result == "gpt-4-turbo"

    def test_finds_model_via_private_delegate(self, eval_runtime):
        """Test finding agent model through _delegate attribute."""
        inner = AgentModelRuntime("gemini-pro")
        wrapper = PrivateDelegateRuntime(inner)
        result = eval_runtime._find_agent_model_in_runtime(wrapper)
        assert result == "gemini-pro"

    def test_returns_none_when_no_model(self, eval_runtime):
        """Test returns None when no runtime implements the protocol."""
        runtime = BaseTestRuntime()
        result = eval_runtime._find_agent_model_in_runtime(runtime)
        assert result is None

    def test_returns_none_for_none_model(self, eval_runtime):
        """Test returns None when runtime returns None for model."""
        runtime = AgentModelRuntime(None)
        result = eval_runtime._find_agent_model_in_runtime(runtime)
        assert result is None


class TestGetAgentModel:
    """Tests for _get_agent_model method."""

    @pytest.fixture
    def context(self):
        """Create eval context."""
        context = UiPathEvalContext()
        context.eval_set = str(
            Path(__file__).parent / "evals" / "eval-sets" / "default.json"
        )
        return context

    async def test_returns_agent_model(self, context):
        """Test that _get_agent_model returns the correct model."""

        async def create_runtime():
            return AgentModelRuntime("gpt-4o-2024-11-20")

        factory = MockFactory(create_runtime)
        event_bus = EventBus()
        trace_manager = UiPathTraceManager()
        eval_runtime = UiPathEvalRuntime(context, factory, trace_manager, event_bus)

        runtime = await create_runtime()
        model = await eval_runtime._get_agent_model(runtime)
        assert model == "gpt-4o-2024-11-20"

    async def test_returns_none_when_no_model(self, context):
        """Test that _get_agent_model returns None when runtime has no model."""

        async def create_runtime():
            return BaseTestRuntime()

        factory = MockFactory(create_runtime)
        event_bus = EventBus()
        trace_manager = UiPathTraceManager()
        eval_runtime = UiPathEvalRuntime(context, factory, trace_manager, event_bus)

        runtime = await create_runtime()
        model = await eval_runtime._get_agent_model(runtime)
        assert model is None

    async def test_returns_model_consistently(self, context):
        """Test that _get_agent_model returns consistent results."""

        async def create_runtime():
            return AgentModelRuntime("consistent-model")

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

        async def create_good_runtime():
            return AgentModelRuntime("model")

        factory = MockFactory(create_good_runtime)
        event_bus = EventBus()
        trace_manager = UiPathTraceManager()
        eval_runtime = UiPathEvalRuntime(context, factory, trace_manager, event_bus)

        # Create a bad runtime that raises during get_agent_model
        class BadRuntime(BaseTestRuntime):
            def get_agent_model(self):
                raise RuntimeError("Get model error")

        bad_runtime = BadRuntime()
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

        async def create_runtime():
            return BaseTestRuntime()

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

        async def create_runtime():
            return BaseTestRuntime()

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

        async def create_runtime():
            return AgentModelRuntime("shared-model")

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


class TestWrappedRuntimeModelResolution:
    """Tests for model resolution through realistic wrapper chains."""

    @pytest.fixture
    def context(self):
        """Create eval context."""
        context = UiPathEvalContext()
        context.eval_set = str(
            Path(__file__).parent / "evals" / "eval-sets" / "default.json"
        )
        return context

    async def test_resolves_model_through_resumable_telemetry_chain(self, context):
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

        async def create_runtime():
            return resumable_runtime

        factory = MockFactory(create_runtime)
        event_bus = EventBus()
        trace_manager = UiPathTraceManager()
        eval_runtime = UiPathEvalRuntime(context, factory, trace_manager, event_bus)

        model = await eval_runtime._get_agent_model(resumable_runtime)
        assert model == "gpt-4o-from-agent-json"
