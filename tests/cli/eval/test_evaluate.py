from pathlib import Path
from typing import Any

from uipath._cli._evals._evaluate import evaluate
from uipath._cli._evals._models._output import UiPathEvalOutput
from uipath._cli._evals._runtime import UiPathEvalContext, UiPathEvalRuntime
from uipath._cli._runtime._contracts import UiPathRuntimeContext, UiPathRuntimeFactory
from uipath._cli._runtime._runtime import UiPathRuntime
from uipath._cli.models.runtime_schema import Entrypoint
from uipath._events._event_bus import EventBus


async def test_evaluate():
    # Arrange
    event_bus = EventBus()
    context = UiPathEvalContext(
        eval_set=str(Path(__file__).parent / "evals" / "eval-sets" / "default.json")
    )

    async def identity(input: Any) -> Any:
        return input

    class TestRuntime(UiPathRuntime):
        async def get_entrypoint(self) -> Entrypoint:
            return Entrypoint(
                file_path="test.py",  # type: ignore[call-arg]
                unique_id="test",
                type="workflow",
                input={"type": "object", "properties": {}},
                output={"type": "object", "properties": {}},
            )

    class MyFactory(UiPathRuntimeFactory[TestRuntime, UiPathRuntimeContext]):
        def __init__(self):
            super().__init__(
                TestRuntime,
                UiPathRuntimeContext,
                runtime_generator=lambda context: TestRuntime(
                    context, executor=identity
                ),
            )

    # Act
    result = await evaluate(MyFactory(), context, event_bus)

    # Assert that the output is json-serializable
    UiPathEvalOutput.model_validate(result.output).model_dump_json()
    assert result.output
    assert (
        result.output["evaluationSetResults"][0]["evaluationRunResults"][0]["result"][
            "score"
        ]
        == 1.0
    )
    assert (
        result.output["evaluationSetResults"][0]["evaluationRunResults"][0][
            "evaluatorId"
        ]
        == "ExactMatchEvaluator"
    )


async def test_evaluate_with_custom_eval_set_run_id():
    """Test that evaluate passes custom eval_set_run_id to the event."""
    # Arrange
    event_bus = EventBus()
    custom_run_id = "custom-test-run-id-12345"
    context = UiPathEvalContext(
        eval_set=str(Path(__file__).parent / "evals" / "eval-sets" / "default.json"),
        eval_set_run_id=custom_run_id,
    )

    async def identity(input: Any) -> Any:
        return input

    class TestRuntime(UiPathRuntime):
        async def get_entrypoint(self) -> Entrypoint:
            return Entrypoint(
                file_path="test.py",  # type: ignore[call-arg]
                unique_id="test",
                type="workflow",
                input={"type": "object", "properties": {}},
                output={"type": "object", "properties": {}},
            )

    class MyFactory(UiPathRuntimeFactory[TestRuntime, UiPathRuntimeContext]):
        def __init__(self):
            super().__init__(
                TestRuntime,
                UiPathRuntimeContext,
                runtime_generator=lambda context: TestRuntime(
                    context, executor=identity
                ),
            )

    factory = MyFactory()

    # Create a runtime instance to verify the eval_set_run_id is passed to context
    async with UiPathEvalRuntime.from_eval_context(
        factory=factory,
        context=context,
        event_bus=event_bus,
    ) as eval_runtime:
        # Assert - verify that the custom run ID was stored in context
        assert eval_runtime.context.eval_set_run_id == custom_run_id
        # execution_id is different from eval_set_run_id - it's always a UUID
        import uuid

        assert eval_runtime.execution_id != custom_run_id
        # Verify execution_id is a valid UUID
        uuid.UUID(eval_runtime.execution_id)


async def test_eval_runtime_uses_custom_eval_set_run_id():
    """Test that UiPathEvalRuntime stores custom eval_set_run_id in context."""
    # Arrange
    custom_run_id = "my-custom-run-id"
    context = UiPathEvalContext(
        eval_set=str(Path(__file__).parent / "evals" / "eval-sets" / "default.json"),
        eval_set_run_id=custom_run_id,
    )
    event_bus = EventBus()

    async def identity(input: Any) -> Any:
        return input

    class TestRuntime(UiPathRuntime):
        async def get_entrypoint(self) -> Entrypoint:
            return Entrypoint(
                file_path="test.py",  # type: ignore[call-arg]
                unique_id="test",
                type="workflow",
                input={"type": "object", "properties": {}},
                output={"type": "object", "properties": {}},
            )

    class MyFactory(UiPathRuntimeFactory[TestRuntime, UiPathRuntimeContext]):
        def __init__(self):
            super().__init__(
                TestRuntime,
                UiPathRuntimeContext,
                runtime_generator=lambda context: TestRuntime(
                    context, executor=identity
                ),
            )

    factory = MyFactory()

    # Act
    runtime = UiPathEvalRuntime(context, factory, event_bus)

    # Assert - verify eval_set_run_id is stored in context
    assert runtime.context.eval_set_run_id == custom_run_id
    # execution_id is separate and always a UUID
    import uuid

    assert runtime.execution_id != custom_run_id
    # Verify execution_id is a valid UUID
    uuid.UUID(runtime.execution_id)


async def test_eval_runtime_generates_uuid_when_no_custom_id():
    """Test that UiPathEvalRuntime generates UUID when no custom eval_set_run_id provided."""
    # Arrange
    context = UiPathEvalContext(
        eval_set=str(Path(__file__).parent / "evals" / "eval-sets" / "default.json"),
    )
    event_bus = EventBus()

    async def identity(input: Any) -> Any:
        return input

    class TestRuntime(UiPathRuntime):
        async def get_entrypoint(self) -> Entrypoint:
            return Entrypoint(
                file_path="test.py",  # type: ignore[call-arg]
                unique_id="test",
                type="workflow",
                input={"type": "object", "properties": {}},
                output={"type": "object", "properties": {}},
            )

    class MyFactory(UiPathRuntimeFactory[TestRuntime, UiPathRuntimeContext]):
        def __init__(self):
            super().__init__(
                TestRuntime,
                UiPathRuntimeContext,
                runtime_generator=lambda context: TestRuntime(
                    context, executor=identity
                ),
            )

    factory = MyFactory()

    # Act
    runtime = UiPathEvalRuntime(context, factory, event_bus)

    # Assert
    # Should be a valid UUID format (36 characters with dashes)
    assert len(runtime.execution_id) == 36
    assert runtime.execution_id.count("-") == 4
