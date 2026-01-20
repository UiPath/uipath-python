from uipath.core.tracing import UiPathTraceManager
from uipath.runtime import (
    UiPathRuntimeFactoryProtocol,
    UiPathRuntimeResult,
)

from uipath._cli._evals._runtime import UiPathEvalContext, UiPathEvalRuntime
from uipath._events._event_bus import EventBus


async def evaluate(
    runtime_factory: UiPathRuntimeFactoryProtocol,
    trace_manager: UiPathTraceManager,
    eval_context: UiPathEvalContext,
    event_bus: EventBus,
) -> UiPathRuntimeResult:
    async with UiPathEvalRuntime(
        factory=runtime_factory,
        context=eval_context,
        trace_manager=trace_manager,
        event_bus=event_bus,
    ) as eval_runtime:
        results = await eval_runtime.execute()
        await event_bus.wait_for_all(timeout=10)
        return results
