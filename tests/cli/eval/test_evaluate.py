from pathlib import Path
from typing import Any

from uipath._cli._evals._evaluate import evaluate
from uipath._cli._evals._runtime import UiPathEvalContext
from uipath._cli._runtime._contracts import UiPathRuntimeContext, UiPathRuntimeFactory
from uipath._cli._runtime._runtime import UiPathRuntime
from uipath._events._event_bus import EventBus


async def test_evaluate():
    # Arrange
    event_bus = EventBus()
    context = UiPathEvalContext(
        eval_set=str(Path(__file__).parent / "evals" / "eval-sets" / "default.json")
    )

    async def identity(input: Any) -> Any:
        return input

    class MyFactory(UiPathRuntimeFactory[UiPathRuntime, UiPathRuntimeContext]):
        def __init__(self):
            super().__init__(
                UiPathRuntime,
                UiPathRuntimeContext,
                runtime_generator=lambda context: UiPathRuntime(
                    context, executor=identity
                ),
            )

    # Act
    result = await evaluate(MyFactory(), context, event_bus)

    # Assert
    assert result.output
    assert (
        result.output["evaluationSetResults"][0]["evaluationRunResults"][0]["result"][
            "score"
        ]
        == 100.0
    )
