from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from tests.cli.utils.workspace_fakes import (
    OPTED_IN,
    REGISTRY,
    FakeSdk,
    FileRuntime,
    MemoryStorage,
    WorkspaceFactory,
)
from uipath.core.events import EventBus
from uipath.core.tracing import UiPathTraceManager
from uipath.eval.helpers import EvalHelpers
from uipath.eval.runtime import UiPathEvalContext, evaluate
from uipath.eval.runtime.events import EvaluationEvents
from uipath.runtime import UiPathRuntimeFactorySettings, UiPathRuntimeStatus

JOB_ID = str(uuid.uuid4())
EVAL_SET = Path(__file__).parent / "evals" / "eval-sets" / "default.json"


async def _eval_context(items: int = 1) -> UiPathEvalContext:
    evaluation_set, _ = EvalHelpers.load_eval_set(str(EVAL_SET))
    first = evaluation_set.evaluations[0]
    evaluation_set.evaluations = [first] + [
        first.model_copy(update={"id": str(uuid.uuid4())}) for _ in range(items - 1)
    ]
    context = UiPathEvalContext()
    context.execution_id = str(uuid.uuid4())
    context.job_id = JOB_ID
    context.evaluation_set = evaluation_set
    context.runtime_schema = await FileRuntime().get_schema()
    context.evaluators = await EvalHelpers.load_evaluators(
        str(EVAL_SET), evaluation_set, agent_model=None
    )
    return context


def _suspending_factory(
    storage: MemoryStorage,
    settings: UiPathRuntimeFactorySettings | None = OPTED_IN,
) -> WorkspaceFactory:
    return WorkspaceFactory(
        FileRuntime(write="draft", status=UiPathRuntimeStatus.SUSPENDED),
        storage=storage,
        settings=settings,
    )


async def test_eval_uploads_each_suspended_item_workspace(sdk: FakeSdk) -> None:
    context = await _eval_context(items=2)
    storage = MemoryStorage()

    await evaluate(
        _suspending_factory(storage), UiPathTraceManager(), context, EventBus()
    )

    item_ids = [item.id for item in context.evaluation_set.evaluations]
    assert list(sdk.attachments.blobs.values()) == [b"draft"] * len(item_ids)
    assert {key[0] for key in storage.values if key[1:] == REGISTRY} == set(item_ids)


async def test_eval_reads_factory_settings_once_for_all_items(sdk: FakeSdk) -> None:
    factory = _suspending_factory(MemoryStorage())

    await evaluate(
        factory, UiPathTraceManager(), await _eval_context(items=2), EventBus()
    )

    assert factory.settings_reads == 1


async def test_eval_set_run_carries_the_factory_agent_type(sdk: FakeSdk) -> None:
    created: list[Any] = []
    event_bus = EventBus()
    event_bus.subscribe(EvaluationEvents.CREATE_EVAL_SET_RUN, created.append)
    settings = UiPathRuntimeFactorySettings(
        managed_workspace=True, agent_type="uipath_coded"
    )

    await evaluate(
        _suspending_factory(MemoryStorage(), settings),
        UiPathTraceManager(),
        await _eval_context(),
        event_bus,
    )
    await event_bus.wait_for_all()

    assert [event.agent_type for event in created] == ["uipath_coded"]
