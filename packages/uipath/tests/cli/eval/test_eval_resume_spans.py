"""Span output across an eval item that suspends in one job and resumes in another."""

import json
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from uipath.core.events import EventBus
from uipath.core.tracing import UiPathTraceManager
from uipath.eval.helpers import EvalHelpers
from uipath.eval.runtime import UiPathEvalContext, evaluate
from uipath.runtime import (
    UiPathExecuteOptions,
    UiPathRuntimeFactorySettings,
    UiPathRuntimeProtocol,
    UiPathRuntimeResult,
    UiPathRuntimeStatus,
    UiPathRuntimeStorageProtocol,
)
from uipath.runtime.schema import UiPathRuntimeSchema

EVAL_SET_PATH = str(Path(__file__).parent / "evals" / "eval-sets" / "default.json")


class InMemoryStorage:
    def __init__(self) -> None:
        self._values: dict[tuple[str, str, str], Any] = {}

    async def set_value(
        self, runtime_id: str, namespace: str, key: str, value: Any
    ) -> None:
        self._values[(runtime_id, namespace, key)] = value

    async def get_value(self, runtime_id: str, namespace: str, key: str) -> Any:
        return self._values.get((runtime_id, namespace, key))


class StubRuntime:
    def __init__(self, result: UiPathRuntimeResult) -> None:
        self._result = result

    async def execute(
        self,
        input: dict[str, Any] | None = None,
        options: UiPathExecuteOptions | None = None,
    ) -> UiPathRuntimeResult:
        return self._result

    async def stream(self, *args: Any, **kwargs: Any) -> Any:
        yield self._result

    async def get_schema(self) -> UiPathRuntimeSchema:
        return _schema()

    async def dispose(self) -> None:
        pass


class StubFactory:
    def __init__(self, storage: InMemoryStorage, result: UiPathRuntimeResult) -> None:
        self._storage = storage
        self._result = result

    def discover_entrypoints(self) -> list[str]:
        return ["test"]

    async def get_storage(self) -> UiPathRuntimeStorageProtocol | None:
        return self._storage

    async def get_settings(self) -> UiPathRuntimeFactorySettings | None:
        return None

    async def new_runtime(
        self, entrypoint: str, runtime_id: str, **kwargs: Any
    ) -> UiPathRuntimeProtocol:
        return StubRuntime(self._result)

    async def dispose(self) -> None:
        pass


def _schema() -> UiPathRuntimeSchema:
    return UiPathRuntimeSchema(
        filePath="test.py",
        uniqueId="test",
        type="agent",
        input={"type": "object", "properties": {}},
        output={"type": "object", "properties": {}},
    )


SUSPENDED = UiPathRuntimeResult(output={}, status=UiPathRuntimeStatus.SUSPENDED)
COMPLETED = UiPathRuntimeResult(
    output={"foo": "bar"}, status=UiPathRuntimeStatus.SUCCESSFUL
)


async def _context(resume: bool, execution_id: str) -> UiPathEvalContext:
    evaluation_set, _ = EvalHelpers.load_eval_set(EVAL_SET_PATH)
    context = UiPathEvalContext()
    context.execution_id = execution_id
    context.evaluation_set = evaluation_set
    context.runtime_schema = _schema()
    context.evaluators = await EvalHelpers.load_evaluators(
        EVAL_SET_PATH, evaluation_set, agent_model=None
    )
    context.resume = resume
    return context


async def _run_job(
    storage: InMemoryStorage,
    result: UiPathRuntimeResult,
    *,
    resume: bool,
    execution_id: str,
) -> list[ReadableSpan]:
    exporter = InMemorySpanExporter()
    trace_manager = UiPathTraceManager()
    trace_manager.tracer_provider.add_span_processor(SimpleSpanProcessor(exporter))
    event_bus = EventBus()
    event_bus.publish = AsyncMock()  # type: ignore[method-assign]

    await evaluate(
        StubFactory(storage, result),
        trace_manager,
        await _context(resume, execution_id),
        event_bus,
    )
    return list(exporter.get_finished_spans())


def _one(spans: list[ReadableSpan], span_type: str) -> ReadableSpan:
    matches = [
        s for s in spans if s.attributes and s.attributes.get("span_type") == span_type
    ]
    assert len(matches) == 1, f"expected one {span_type} span, got {len(matches)}"
    return matches[0]


def _output(span: ReadableSpan) -> dict[str, Any]:
    assert span.attributes is not None
    return json.loads(str(span.attributes["output"]))


@pytest.fixture
async def suspended_then_resumed() -> tuple[list[ReadableSpan], list[ReadableSpan]]:
    storage = InMemoryStorage()
    execution_id = str(uuid.uuid4())
    suspend_spans = await _run_job(
        storage, SUSPENDED, resume=False, execution_id=execution_id
    )
    resume_spans = await _run_job(
        storage, COMPLETED, resume=True, execution_id=execution_id
    )
    return suspend_spans, resume_spans


class TestResumedEvaluationSpans:
    async def test_evaluation_span_reports_scores(self, suspended_then_resumed):
        _, resume_spans = suspended_then_resumed

        evaluation = _one(resume_spans, "evaluation")

        assert _output(evaluation)["scores"] == {"ExactMatchEvaluator": 100.0}

    async def test_eval_set_run_span_reports_scores(self, suspended_then_resumed):
        _, resume_spans = suspended_then_resumed

        eval_set_run = _one(resume_spans, "eval_set_run")

        assert _output(eval_set_run)["scores"] == {"ExactMatchEvaluator": 100.0}

    async def test_resumed_spans_keep_original_ids_and_start(
        self, suspended_then_resumed
    ):
        suspend_spans, resume_spans = suspended_then_resumed

        for span_type in ("eval_set_run", "evaluation"):
            before = _one(suspend_spans, span_type)
            after = _one(resume_spans, span_type)
            assert before.context is not None and after.context is not None
            assert after.context.span_id == before.context.span_id
            assert after.context.trace_id == before.context.trace_id
            assert after.parent == before.parent
            assert after.start_time == before.start_time

    async def test_evaluator_span_keeps_execution_id(self, suspended_then_resumed):
        _, resume_spans = suspended_then_resumed

        evaluation = _one(resume_spans, "evaluation")
        evaluator = _one(resume_spans, "evaluator")

        assert evaluator.attributes is not None and evaluation.attributes is not None
        assert evaluator.attributes.get("execution.id") == evaluation.attributes.get(
            "execution.id"
        )
        assert evaluator.parent is not None and evaluation.context is not None
        assert evaluator.parent.span_id == evaluation.context.span_id
