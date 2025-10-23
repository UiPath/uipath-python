from uipath._cli._runtime._contracts import (
    UiPathBaseRuntime,
    UiPathRuntimeContext,
    UiPathRuntimeFactory,
)
from uipath._cli._runtime._runtime import UiPathScriptRuntime


def generate_runtime_factory() -> UiPathRuntimeFactory[
    UiPathBaseRuntime, UiPathRuntimeContext
]:
    runtime_factory: UiPathRuntimeFactory[UiPathBaseRuntime, UiPathRuntimeContext] = (
        UiPathRuntimeFactory(
            UiPathScriptRuntime,
            UiPathRuntimeContext,
            context_generator=lambda **kwargs: UiPathRuntimeContext.with_defaults(
                **kwargs
            ),
        )
    )
    return runtime_factory
