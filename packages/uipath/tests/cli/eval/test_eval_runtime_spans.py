"""Tests for eval runtime span creation.

Verifies that the eval runtime methods produce the correct OpenTelemetry spans:
1. "Evaluation Set Run" - span_type: "eval_set_run" (from execute())
2. "Evaluation" - span_type: "evaluation" (from _execute_eval())
3. "Evaluator: {name}" - span_type: "evaluator" (from run_evaluator())
4. "Evaluation output" - span_type: "evalOutput" (from run_evaluator())
"""

import json
import uuid
from contextlib import contextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from uipath.eval.evaluators import BaseEvaluator
from uipath.eval.models import NumericEvaluationResult
from uipath.eval.models.evaluation_set import EvaluationItem, EvaluationSet
from uipath.eval.runtime import UiPathEvalContext, UiPathEvalRuntime
from uipath.runtime.schema import UiPathRuntimeSchema


# --- Test infrastructure ---


class MockSpan:
    """Mock span that captures set_attribute and set_status calls."""

    def __init__(self, name: str, attributes: dict[str, Any] | None = None):
        self.name = name
        self.attributes = dict(attributes) if attributes else {}
        self._status = None

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def set_status(self, status: Any) -> None:
        self._status = status

    def __enter__(self) -> "MockSpan":
        return self

    def __exit__(self, *args: Any) -> None:
        pass


class SpanCapturingTracer:
    """Tracer that captures all created spans for verification."""

    def __init__(self) -> None:
        self.captured_spans: list[MockSpan] = []

    @contextmanager
    def start_as_current_span(
        self, name: str, attributes: dict[str, Any] | None = None
    ):
        mock_span = MockSpan(name, attributes)
        self.captured_spans.append(mock_span)
        yield mock_span

    def get_spans_by_type(self, span_type: str) -> list[MockSpan]:
        return [
            s
            for s in self.captured_spans
            if s.attributes.get("span_type") == span_type
        ]

    def get_spans_by_attr(self, key: str, value: str) -> list[MockSpan]:
        return [s for s in self.captured_spans if s.attributes.get(key) == value]

    def get_span_by_name(self, name: str) -> MockSpan | None:
        for span in self.captured_spans:
            if span.name == name:
                return span
        return None


def create_eval_context(**kwargs: Any) -> UiPathEvalContext:
    """Create UiPathEvalContext with sensible defaults, overridable via kwargs."""
    context = UiPathEvalContext()

    if "execution_id" not in kwargs:
        context.execution_id = str(uuid.uuid4())
    if "runtime_schema" not in kwargs:
        context.runtime_schema = UiPathRuntimeSchema(
            filePath="test.py",
            uniqueId="test",
            type="workflow",
            input={"type": "object", "properties": {}},
            output={"type": "object", "properties": {}},
        )
    if "evaluation_set" not in kwargs:
        context.evaluation_set = EvaluationSet(
            id="test-eval-set",
            name="Test Evaluation Set",
            evaluations=[],
        )
    if "evaluators" not in kwargs:
        context.evaluators = []

    for key, value in kwargs.items():
        setattr(context, key, value)

    return context


def make_mock_execution_output(
    output: dict[str, Any] | None = None,
    error: Any = None,
    status: str = "successful",
) -> MagicMock:
    """Create a mock execution output from execute_runtime."""
    mock = MagicMock()
    mock.result.output = output or {"result": "ok"}
    mock.result.error = error
    mock.result.status = status
    mock.result.trigger = None
    mock.result.triggers = None
    mock.spans = []
    mock.logs = []
    mock.execution_time = 1.0
    return mock


def make_runtime(
    capturing_tracer: SpanCapturingTracer, **context_kwargs: Any
) -> UiPathEvalRuntime:
    """Create a UiPathEvalRuntime wired to a SpanCapturingTracer."""
    mock_trace_manager = MagicMock()
    mock_trace_manager.tracer_provider.get_tracer.return_value = capturing_tracer
    mock_trace_manager.tracer_span_processors = []

    mock_factory = MagicMock()
    mock_factory.new_runtime = AsyncMock(return_value=AsyncMock())

    mock_event_bus = MagicMock()
    mock_event_bus.publish = AsyncMock()

    context = create_eval_context(**context_kwargs)

    return UiPathEvalRuntime(
        context=context,
        factory=mock_factory,
        trace_manager=mock_trace_manager,
        event_bus=mock_event_bus,
    )


def make_evaluator(
    name: str = "AccuracyEvaluator",
    evaluator_id: str = "accuracy-eval",
    score: float = 0.95,
    details: Any = None,
) -> MagicMock:
    """Create a mock evaluator that returns a fixed score."""
    evaluator = MagicMock(spec=BaseEvaluator)
    evaluator.id = evaluator_id
    evaluator.name = name
    evaluator.validate_and_evaluate_criteria = AsyncMock(
        return_value=NumericEvaluationResult(score=score, details=details)
    )
    return evaluator


def make_eval_item(
    item_id: str = "item-123",
    name: str = "Test Evaluation",
    inputs: dict[str, Any] | None = None,
    evaluation_criterias: dict[str, Any] | None = None,
) -> EvaluationItem:
    """Create an EvaluationItem for testing."""
    return EvaluationItem(
        id=item_id,
        name=name,
        inputs=inputs or {},
        evaluation_criterias=evaluation_criterias or {},
    )


# --- Test classes ---


class TestEvalSetRunSpan:
    """Tests that runtime.execute() creates the 'Evaluation Set Run' span."""

    @pytest.mark.asyncio
    async def test_execute_creates_eval_set_run_span(self) -> None:
        tracer = SpanCapturingTracer()
        runtime = make_runtime(tracer)

        with patch.object(
            runtime,
            "initiate_evaluation",
            new=AsyncMock(
                return_value=(
                    MagicMock(name="Test Set", evaluations=[]),
                    [],
                    iter([]),
                )
            ),
        ):
            try:
                await runtime.execute()
            except Exception:
                pass

        spans = tracer.get_spans_by_type("eval_set_run")
        assert len(spans) >= 1
        assert spans[0].name == "Evaluation Set Run"

    @pytest.mark.asyncio
    async def test_eval_set_run_id_included_when_provided(self) -> None:
        tracer = SpanCapturingTracer()
        runtime = make_runtime(tracer, eval_set_run_id="custom-run-abc")

        with patch.object(
            runtime,
            "initiate_evaluation",
            new=AsyncMock(
                return_value=(
                    MagicMock(name="Test Set", evaluations=[]),
                    [],
                    iter([]),
                )
            ),
        ):
            try:
                await runtime.execute()
            except Exception:
                pass

        span = tracer.get_spans_by_type("eval_set_run")[0]
        assert span.attributes["eval_set_run_id"] == "custom-run-abc"

    @pytest.mark.asyncio
    async def test_eval_set_run_id_excluded_when_not_provided(self) -> None:
        tracer = SpanCapturingTracer()
        runtime = make_runtime(tracer)

        with patch.object(
            runtime,
            "initiate_evaluation",
            new=AsyncMock(
                return_value=(
                    MagicMock(name="Test Set", evaluations=[]),
                    [],
                    iter([]),
                )
            ),
        ):
            try:
                await runtime.execute()
            except Exception:
                pass

        span = tracer.get_spans_by_type("eval_set_run")[0]
        assert "eval_set_run_id" not in span.attributes

    @pytest.mark.asyncio
    async def test_eval_set_run_span_has_custom_instrumentation_flag(self) -> None:
        tracer = SpanCapturingTracer()
        runtime = make_runtime(tracer)

        with patch.object(
            runtime,
            "initiate_evaluation",
            new=AsyncMock(
                return_value=(
                    MagicMock(name="Test Set", evaluations=[]),
                    [],
                    iter([]),
                )
            ),
        ):
            try:
                await runtime.execute()
            except Exception:
                pass

        span = tracer.get_spans_by_type("eval_set_run")[0]
        assert span.attributes["uipath.custom_instrumentation"] is True

    @pytest.mark.asyncio
    async def test_eval_set_run_span_configured_with_metadata(self) -> None:
        """After evaluations complete, span gets agentId, agentName, schemas.

        This requires the full pipeline to complete (initiate_evaluation ->
        execute_parallel -> compute_evaluator_scores -> configure_eval_set_run_span).
        We mock execute_parallel to return an empty list so the pipeline completes.
        """
        from uipath.eval.runtime.runtime import execute_parallel

        tracer = SpanCapturingTracer()
        runtime = make_runtime(tracer)

        eval_set = MagicMock()
        eval_set.name = "Test Set"
        eval_set.evaluations = []

        with patch.object(
            runtime,
            "initiate_evaluation",
            new=AsyncMock(
                return_value=(eval_set, [], iter([]))
            ),
        ), patch(
            "uipath.eval.runtime.runtime.execute_parallel",
            new=AsyncMock(return_value=[]),
        ):
            await runtime.execute()

        span = tracer.get_spans_by_type("eval_set_run")[0]
        # configure_eval_set_run_span sets these via set_attribute
        assert span.attributes.get("agentName") == "N/A"
        assert "agentId" in span.attributes
        assert "inputSchema" in span.attributes
        assert "outputSchema" in span.attributes


class TestEvaluationSpan:
    """Tests that runtime._execute_eval() creates the 'Evaluation' span."""

    @pytest.mark.asyncio
    async def test_execute_eval_creates_evaluation_span(self) -> None:
        tracer = SpanCapturingTracer()
        runtime = make_runtime(tracer)
        eval_item = make_eval_item()

        with patch.object(
            runtime,
            "execute_runtime",
            new=AsyncMock(return_value=make_mock_execution_output()),
        ):
            await runtime._execute_eval(eval_item, [])

        spans = tracer.get_spans_by_type("evaluation")
        assert len(spans) == 1
        assert spans[0].name == "Evaluation"

    @pytest.mark.asyncio
    async def test_evaluation_span_has_eval_item_attributes(self) -> None:
        tracer = SpanCapturingTracer()
        runtime = make_runtime(tracer)
        eval_item = make_eval_item(item_id="my-item-99", name="My Special Eval")

        with patch.object(
            runtime,
            "execute_runtime",
            new=AsyncMock(return_value=make_mock_execution_output()),
        ):
            await runtime._execute_eval(eval_item, [])

        span = tracer.get_spans_by_type("evaluation")[0]
        assert span.attributes["eval_item_id"] == "my-item-99"
        assert span.attributes["eval_item_name"] == "My Special Eval"

    @pytest.mark.asyncio
    async def test_evaluation_span_has_execution_id_from_eval_item(self) -> None:
        tracer = SpanCapturingTracer()
        runtime = make_runtime(tracer)
        eval_item = make_eval_item(item_id="item-abc")

        with patch.object(
            runtime,
            "execute_runtime",
            new=AsyncMock(return_value=make_mock_execution_output()),
        ):
            await runtime._execute_eval(eval_item, [])

        span = tracer.get_spans_by_type("evaluation")[0]
        assert span.attributes["execution.id"] == "item-abc"

    @pytest.mark.asyncio
    async def test_evaluation_span_has_custom_instrumentation_flag(self) -> None:
        tracer = SpanCapturingTracer()
        runtime = make_runtime(tracer)
        eval_item = make_eval_item()

        with patch.object(
            runtime,
            "execute_runtime",
            new=AsyncMock(return_value=make_mock_execution_output()),
        ):
            await runtime._execute_eval(eval_item, [])

        span = tracer.get_spans_by_type("evaluation")[0]
        assert span.attributes["uipath.custom_instrumentation"] is True

    @pytest.mark.asyncio
    async def test_evaluation_span_configured_with_scores_after_evaluators(
        self,
    ) -> None:
        tracer = SpanCapturingTracer()
        runtime = make_runtime(tracer)

        evaluator = make_evaluator(
            name="Accuracy", evaluator_id="acc-eval", score=0.85
        )
        eval_item = make_eval_item(evaluation_criterias={"acc-eval": {}})

        with patch.object(
            runtime,
            "execute_runtime",
            new=AsyncMock(return_value=make_mock_execution_output()),
        ):
            await runtime._execute_eval(eval_item, [evaluator])

        span = tracer.get_spans_by_type("evaluation")[0]
        assert "output" in span.attributes
        output = json.loads(span.attributes["output"])
        assert "scores" in output
        assert "Accuracy" in output["scores"]

    @pytest.mark.asyncio
    async def test_evaluation_span_has_metadata_after_execution(self) -> None:
        tracer = SpanCapturingTracer()
        runtime = make_runtime(tracer)
        eval_item = make_eval_item(inputs={"query": "test"})

        with patch.object(
            runtime,
            "execute_runtime",
            new=AsyncMock(return_value=make_mock_execution_output()),
        ):
            await runtime._execute_eval(eval_item, [])

        span = tracer.get_spans_by_type("evaluation")[0]
        assert span.attributes.get("agentName") == "N/A"
        assert "agentId" in span.attributes


class TestEvaluatorSpan:
    """Tests that runtime.run_evaluator() creates the 'Evaluator: {name}' span."""

    @pytest.mark.asyncio
    async def test_run_evaluator_creates_evaluator_span(self) -> None:
        tracer = SpanCapturingTracer()
        runtime = make_runtime(tracer)
        evaluator = make_evaluator(name="AccuracyEvaluator", evaluator_id="acc-1")
        eval_item = make_eval_item()
        execution_output = make_mock_execution_output()

        await runtime.run_evaluator(
            evaluator=evaluator,
            execution_output=execution_output,
            eval_item=eval_item,
            evaluation_criteria=None,
        )

        spans = tracer.get_spans_by_type("evaluator")
        assert len(spans) == 1
        assert spans[0].name == "Evaluator: AccuracyEvaluator"

    @pytest.mark.asyncio
    async def test_evaluator_span_has_correct_attributes(self) -> None:
        tracer = SpanCapturingTracer()
        runtime = make_runtime(tracer)
        evaluator = make_evaluator(
            name="RelevanceEvaluator", evaluator_id="rel-eval-42"
        )
        eval_item = make_eval_item(item_id="eval-item-77")
        execution_output = make_mock_execution_output()

        await runtime.run_evaluator(
            evaluator=evaluator,
            execution_output=execution_output,
            eval_item=eval_item,
            evaluation_criteria=None,
        )

        span = tracer.get_spans_by_type("evaluator")[0]
        assert span.attributes["evaluator_id"] == "rel-eval-42"
        assert span.attributes["evaluator_name"] == "RelevanceEvaluator"
        assert span.attributes["eval_item_id"] == "eval-item-77"
        assert span.attributes["uipath.custom_instrumentation"] is True

    @pytest.mark.asyncio
    async def test_multiple_evaluators_create_separate_spans(self) -> None:
        tracer = SpanCapturingTracer()
        runtime = make_runtime(tracer)
        eval_item = make_eval_item()
        execution_output = make_mock_execution_output()

        names = ["Accuracy", "Relevance", "Fluency"]
        for name in names:
            evaluator = make_evaluator(name=name, evaluator_id=f"{name.lower()}-id")
            await runtime.run_evaluator(
                evaluator=evaluator,
                execution_output=execution_output,
                eval_item=eval_item,
                evaluation_criteria=None,
            )

        spans = tracer.get_spans_by_type("evaluator")
        assert len(spans) == 3
        span_names = [s.name for s in spans]
        assert "Evaluator: Accuracy" in span_names
        assert "Evaluator: Relevance" in span_names
        assert "Evaluator: Fluency" in span_names


class TestEvaluationOutputSpan:
    """Tests that run_evaluator() creates the child 'Evaluation output' span."""

    @pytest.mark.asyncio
    async def test_run_evaluator_creates_eval_output_span(self) -> None:
        tracer = SpanCapturingTracer()
        runtime = make_runtime(tracer)
        evaluator = make_evaluator(score=0.9)
        eval_item = make_eval_item()
        execution_output = make_mock_execution_output()

        await runtime.run_evaluator(
            evaluator=evaluator,
            execution_output=execution_output,
            eval_item=eval_item,
            evaluation_criteria=None,
        )

        output_spans = tracer.get_spans_by_attr("span.type", "evalOutput")
        assert len(output_spans) == 1
        assert output_spans[0].name == "Evaluation output"

    @pytest.mark.asyncio
    async def test_eval_output_span_has_score_and_evaluator_id(self) -> None:
        tracer = SpanCapturingTracer()
        runtime = make_runtime(tracer)
        evaluator = make_evaluator(
            evaluator_id="my-eval-id", score=0.75
        )
        eval_item = make_eval_item()
        execution_output = make_mock_execution_output()

        await runtime.run_evaluator(
            evaluator=evaluator,
            execution_output=execution_output,
            eval_item=eval_item,
            evaluation_criteria=None,
        )

        span = tracer.get_spans_by_attr("span.type", "evalOutput")[0]
        assert span.attributes["value"] == 0.75
        assert span.attributes["evaluatorId"] == "my-eval-id"

    @pytest.mark.asyncio
    async def test_eval_output_span_has_openinference_kind(self) -> None:
        tracer = SpanCapturingTracer()
        runtime = make_runtime(tracer)
        evaluator = make_evaluator()
        eval_item = make_eval_item()
        execution_output = make_mock_execution_output()

        await runtime.run_evaluator(
            evaluator=evaluator,
            execution_output=execution_output,
            eval_item=eval_item,
            evaluation_criteria=None,
        )

        span = tracer.get_spans_by_attr("span.type", "evalOutput")[0]
        assert span.attributes["openinference.span.kind"] == "CHAIN"

    @pytest.mark.asyncio
    async def test_eval_output_span_justification_from_pydantic_details(self) -> None:
        class EvalDetails(BaseModel):
            justification: str
            extra: str = "ignored"

        details = EvalDetails(justification="Semantically equivalent output")
        tracer = SpanCapturingTracer()
        runtime = make_runtime(tracer)
        evaluator = make_evaluator(score=0.92, details=details)
        eval_item = make_eval_item()
        execution_output = make_mock_execution_output()

        await runtime.run_evaluator(
            evaluator=evaluator,
            execution_output=execution_output,
            eval_item=eval_item,
            evaluation_criteria=None,
        )

        span = tracer.get_spans_by_attr("span.type", "evalOutput")[0]
        assert span.attributes["justification"] == "Semantically equivalent output"

    @pytest.mark.asyncio
    async def test_eval_output_span_justification_from_string_details(self) -> None:
        tracer = SpanCapturingTracer()
        runtime = make_runtime(tracer)
        evaluator = make_evaluator(score=0.8, details="Good accuracy overall")
        eval_item = make_eval_item()
        execution_output = make_mock_execution_output()

        await runtime.run_evaluator(
            evaluator=evaluator,
            execution_output=execution_output,
            eval_item=eval_item,
            evaluation_criteria=None,
        )

        span = tracer.get_spans_by_attr("span.type", "evalOutput")[0]
        assert span.attributes["justification"] == "Good accuracy overall"

    @pytest.mark.asyncio
    async def test_eval_output_span_no_justification_when_no_details(self) -> None:
        tracer = SpanCapturingTracer()
        runtime = make_runtime(tracer)
        evaluator = make_evaluator(score=1.0, details=None)
        eval_item = make_eval_item()
        execution_output = make_mock_execution_output()

        await runtime.run_evaluator(
            evaluator=evaluator,
            execution_output=execution_output,
            eval_item=eval_item,
            evaluation_criteria=None,
        )

        span = tracer.get_spans_by_attr("span.type", "evalOutput")[0]
        assert "justification" not in span.attributes

    @pytest.mark.asyncio
    async def test_eval_output_span_output_has_normalized_score(self) -> None:
        tracer = SpanCapturingTracer()
        runtime = make_runtime(tracer)
        evaluator = make_evaluator(score=0.85)
        eval_item = make_eval_item()
        execution_output = make_mock_execution_output()

        await runtime.run_evaluator(
            evaluator=evaluator,
            execution_output=execution_output,
            eval_item=eval_item,
            evaluation_criteria=None,
        )

        span = tracer.get_spans_by_attr("span.type", "evalOutput")[0]
        output = json.loads(span.attributes["output"])
        # 0.85 normalized to 0-100 range
        assert output["score"] == 85.0

    @pytest.mark.asyncio
    async def test_eval_output_span_output_type_always_one(self) -> None:
        tracer = SpanCapturingTracer()
        runtime = make_runtime(tracer)
        evaluator = make_evaluator(score=0.5)
        eval_item = make_eval_item()
        execution_output = make_mock_execution_output()

        await runtime.run_evaluator(
            evaluator=evaluator,
            execution_output=execution_output,
            eval_item=eval_item,
            evaluation_criteria=None,
        )

        span = tracer.get_spans_by_attr("span.type", "evalOutput")[0]
        output = json.loads(span.attributes["output"])
        assert output["type"] == 1


class TestSpanHierarchy:
    """Tests that spans are created in the correct order/nesting."""

    @pytest.mark.asyncio
    async def test_run_evaluator_creates_both_evaluator_and_output_spans(self) -> None:
        tracer = SpanCapturingTracer()
        runtime = make_runtime(tracer)
        evaluator = make_evaluator(name="TestEval")
        eval_item = make_eval_item()
        execution_output = make_mock_execution_output()

        await runtime.run_evaluator(
            evaluator=evaluator,
            execution_output=execution_output,
            eval_item=eval_item,
            evaluation_criteria=None,
        )

        # Should have both an evaluator span and an eval output span
        evaluator_spans = tracer.get_spans_by_type("evaluator")
        output_spans = tracer.get_spans_by_attr("span.type", "evalOutput")
        assert len(evaluator_spans) == 1
        assert len(output_spans) == 1

    @pytest.mark.asyncio
    async def test_eval_output_span_created_after_evaluator_span(self) -> None:
        tracer = SpanCapturingTracer()
        runtime = make_runtime(tracer)
        evaluator = make_evaluator(name="OrderTest")
        eval_item = make_eval_item()
        execution_output = make_mock_execution_output()

        await runtime.run_evaluator(
            evaluator=evaluator,
            execution_output=execution_output,
            eval_item=eval_item,
            evaluation_criteria=None,
        )

        # In the captured list, the evaluator span should appear before the output span
        span_names = [s.name for s in tracer.captured_spans]
        evaluator_idx = span_names.index("Evaluator: OrderTest")
        output_idx = span_names.index("Evaluation output")
        assert evaluator_idx < output_idx
