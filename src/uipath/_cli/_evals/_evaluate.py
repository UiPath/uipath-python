from typing import TypeVar

from uipath._cli._evals._runtime import UiPathEvalContext, UiPathEvalRuntime
from uipath._cli._runtime._contracts import (
    UiPathBaseRuntime,
    UiPathRuntimeContext,
    UiPathRuntimeFactory,
    UiPathRuntimeResult,
)
from uipath._events._event_bus import EventBus

T = TypeVar("T", bound=UiPathBaseRuntime)
C = TypeVar("C", bound=UiPathRuntimeContext)


async def evaluate(
    runtime_factory: UiPathRuntimeFactory[T, C],
    eval_context: UiPathEvalContext,
    event_bus: EventBus,
) -> UiPathRuntimeResult:
    async with UiPathEvalRuntime.from_eval_context(
        factory=runtime_factory,
        context=eval_context,
        event_bus=event_bus,
    ) as eval_runtime:
        results = await eval_runtime.execute()
        await event_bus.wait_for_all(timeout=10)
        return results
