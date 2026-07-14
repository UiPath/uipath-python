"""Protocol conformance for uipath-runtime protocol implementations.

Every protocol-annotated assignment below is a typed boundary: mypy verifies
the implementation against the protocol surface of the installed
uipath-runtime version. A dependency bump that adds or changes protocol
members fails typecheck on these lines until the implementations catch up.

Deliberately construction-only: no runtime behavior is exercised here.
"""

import uuid

from uipath.core.events import EventBus
from uipath.core.tracing import UiPathTraceManager
from uipath.eval.runtime import UiPathEvalContext, UiPathEvalRuntime
from uipath.functions import (
    UiPathDebugFunctionsRuntime,
    UiPathFunctionsRuntime,
    UiPathFunctionsRuntimeFactory,
)
from uipath.platform.resume_triggers import (
    UiPathResumeTriggerCreator,
    UiPathResumeTriggerReader,
)
from uipath.runtime import (
    UiPathRuntimeFactoryProtocol,
    UiPathRuntimeProtocol,
)
from uipath.runtime.resumable.protocols import (
    UiPathResumeTriggerCreatorProtocol,
    UiPathResumeTriggerReaderProtocol,
)


def test_functions_runtime_satisfies_runtime_protocol() -> None:
    runtime: UiPathRuntimeProtocol = UiPathFunctionsRuntime(
        file_path="main.py",
        function_name="main",
        entrypoint_name="main",
    )

    # the debug wrapper's `delegate` parameter is protocol-typed: passing the
    # real functions runtime through it is a second typed boundary, and the
    # wrapper itself must satisfy the protocol too
    debug_runtime: UiPathRuntimeProtocol = UiPathDebugFunctionsRuntime(
        delegate=runtime,
        entrypoint_path="main.py",
        function_name="main",
    )

    assert debug_runtime is not None


def test_functions_factory_satisfies_factory_protocol() -> None:
    factory: UiPathRuntimeFactoryProtocol = UiPathFunctionsRuntimeFactory()

    # the eval runtime's `factory` parameter is protocol-typed: the real
    # functions factory flows through it. UiPathEvalRuntime itself is a
    # specialized runtime (no stream, argument-less execute) and is
    # deliberately NOT pinned against UiPathRuntimeProtocol.
    context = UiPathEvalContext()
    context.execution_id = str(uuid.uuid4())
    eval_runtime = UiPathEvalRuntime(
        context=context,
        factory=factory,
        trace_manager=UiPathTraceManager(),
        event_bus=EventBus(),
    )

    assert eval_runtime is not None


def test_standalone_trigger_classes_satisfy_protocols() -> None:
    # cover direct consumers of the standalone creator/reader classes
    creator: UiPathResumeTriggerCreatorProtocol = UiPathResumeTriggerCreator()
    reader: UiPathResumeTriggerReaderProtocol = UiPathResumeTriggerReader()

    assert creator is not None
    assert reader is not None
