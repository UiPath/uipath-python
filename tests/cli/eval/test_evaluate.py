from pathlib import Path
from typing import Any, AsyncGenerator

from pydantic import BaseModel
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
from uipath._cli._evals._models._output import UiPathEvalOutput
from uipath._cli._evals._runtime import UiPathEvalContext, UiPathEvalRuntime
from uipath._events._event_bus import EventBus


async def test_evaluate():
    event_bus = EventBus()
    trace_manager = UiPathTraceManager()
    context = UiPathEvalContext()
    context.eval_set = str(
        Path(__file__).parent / "evals" / "eval-sets" / "default.json"
    )

    async def identity(input: dict[str, Any]) -> dict[str, Any]:
        return input

    class TestRuntime:
        def __init__(self, executor):
            self.executor = executor

        async def execute(
            self,
            input: dict[str, Any] | None = None,
            options: UiPathExecuteOptions | None = None,
        ) -> UiPathRuntimeResult:
            result = await self.executor(input or {})
            return UiPathRuntimeResult(
                output=result,
                status=UiPathRuntimeStatus.SUCCESSFUL,
            )

        async def stream(
            self,
            input: dict[str, Any] | None = None,
            options: UiPathStreamOptions | None = None,
        ) -> AsyncGenerator[UiPathRuntimeEvent, None]:
            result = await self.executor(input or {})
            yield UiPathRuntimeResult(
                output=result,
                status=UiPathRuntimeStatus.SUCCESSFUL,
            )

        async def get_schema(self) -> UiPathRuntimeSchema:
            return UiPathRuntimeSchema(
                filePath="test.py",
                uniqueId="test",
                type="workflow",
                input={"type": "object", "properties": {}},
                output={"type": "object", "properties": {}},
            )

        async def dispose(self) -> None:
            pass

    class TestFactory:
        def __init__(self, executor):
            self.executor = executor

        def discover_entrypoints(self) -> list[str]:
            return ["test"]

        async def discover_runtimes(self) -> list[UiPathRuntimeProtocol]:
            return [TestRuntime(self.executor)]

        async def new_runtime(
            self, entrypoint: str, runtime_id: str
        ) -> UiPathRuntimeProtocol:
            return TestRuntime(self.executor)

        async def dispose(self) -> None:
            pass

    factory = TestFactory(identity)

    # Act
    result = await evaluate(factory, trace_manager, context, event_bus)

    # Assert that the output is json-serializable
    UiPathEvalOutput.model_validate(result.output).model_dump_json()
    assert result.output
    output_dict = (
        result.output.model_dump()
        if isinstance(result.output, BaseModel)
        else result.output
    )
    assert isinstance(output_dict, dict)
    assert (
        output_dict["evaluationSetResults"][0]["evaluationRunResults"][0]["result"][
            "score"
        ]
        == 1.0
    )
    assert (
        output_dict["evaluationSetResults"][0]["evaluationRunResults"][0]["evaluatorId"]
        == "ExactMatchEvaluator"
    )


async def test_eval_runtime_generates_uuid_when_no_custom_id():
    """Test that UiPathEvalRuntime generates UUID when no custom eval_set_run_id provided."""
    # Arrange
    context = UiPathEvalContext()
    context.eval_set = str(
        Path(__file__).parent / "evals" / "eval-sets" / "default.json"
    )
    event_bus = EventBus()
    trace_manager = UiPathTraceManager()

    async def identity(input: dict[str, Any]) -> dict[str, Any]:
        return input

    # Mock runtime that implements the protocol
    class TestRuntime:
        def __init__(self, executor):
            self.executor = executor

        async def execute(
            self,
            input: dict[str, Any] | None = None,
            options: UiPathExecuteOptions | None = None,
        ) -> UiPathRuntimeResult:
            result = await self.executor(input or {})
            return UiPathRuntimeResult(
                output=result,
                status=UiPathRuntimeStatus.SUCCESSFUL,
            )

        async def stream(
            self,
            input: dict[str, Any] | None = None,
            options: UiPathStreamOptions | None = None,
        ) -> AsyncGenerator[UiPathRuntimeEvent, None]:
            result = await self.executor(input or {})
            yield UiPathRuntimeResult(
                output=result,
                status=UiPathRuntimeStatus.SUCCESSFUL,
            )

        async def get_schema(self) -> UiPathRuntimeSchema:
            return UiPathRuntimeSchema(
                filePath="test.py",
                uniqueId="test",
                type="workflow",
                input={"type": "object", "properties": {}},
                output={"type": "object", "properties": {}},
            )

        async def dispose(self) -> None:
            pass

    class TestFactory:
        def __init__(self, executor):
            self.executor = executor

        def discover_entrypoints(self) -> list[str]:
            return ["test"]

        async def discover_runtimes(self) -> list[UiPathRuntimeProtocol]:
            return [TestRuntime(self.executor)]

        async def new_runtime(
            self, entrypoint: str, runtime_id: str
        ) -> UiPathRuntimeProtocol:
            return TestRuntime(self.executor)

        async def dispose(self) -> None:
            pass

    factory = TestFactory(identity)

    # Act
    runtime = UiPathEvalRuntime(context, factory, trace_manager, event_bus)

    # Assert
    # Should be a valid UUID format (36 characters with dashes)
    assert len(runtime.execution_id) == 36
    assert runtime.execution_id.count("-") == 4
