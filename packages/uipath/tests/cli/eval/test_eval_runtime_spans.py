"""Tests for eval runtime span creation.

Verifies that running evaluations produces the correct OpenTelemetry span tree:

    "Evaluation Set Run" (span_type: "eval_set_run")
      └── "Evaluation" (span_type: "evaluation")  — one per eval item
            └── "Evaluator: {name}" (span_type: "evaluator")  — one per evaluator
                  └── "Evaluation output" (span.type: "evalOutput")  — the score

Every test runs the full pipeline via execute(). Only execute_runtime (the
actual agent invocation) is mocked — everything else runs for real.
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


def make_evaluator(
    name: str = "MockEvaluator",
    evaluator_id: str = "mock-evaluator",
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
    # reduce_scores is called by compute_evaluator_scores to aggregate across items
    evaluator.reduce_scores = lambda results: (
        sum(r.score for r in results) / len(results) if results else 0.0
    )
    return evaluator


def make_eval_item(
    item_id: str = "eval-item-default",
    name: str = "Default Test Case",
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


async def run_evaluation(
    eval_items: list[EvaluationItem],
    evaluators: list[MagicMock],
    execution_output: MagicMock | None = None,
    **context_kwargs: Any,
) -> tuple[SpanCapturingTracer, UiPathEvalRuntime]:
    """Run execute() through the full pipeline and return the tracer + runtime.

    Sets up the runtime with real eval items and evaluators, mocks only
    execute_runtime, and runs execute() to completion.
    """
    tracer = SpanCapturingTracer()

    mock_trace_manager = MagicMock()
    mock_trace_manager.tracer_provider.get_tracer.return_value = tracer
    mock_trace_manager.tracer_span_processors = []

    mock_factory = MagicMock()
    mock_factory.new_runtime = AsyncMock(return_value=AsyncMock())

    mock_event_bus = MagicMock()
    mock_event_bus.publish = AsyncMock()

    context = UiPathEvalContext()
    context.execution_id = context_kwargs.pop(
        "execution_id", str(uuid.uuid4())
    )
    context.runtime_schema = context_kwargs.pop(
        "runtime_schema",
        UiPathRuntimeSchema(
            filePath="test.py",
            uniqueId="test",
            type="workflow",
            input={"type": "object", "properties": {"x": {"type": "number"}}},
            output={"type": "object", "properties": {}},
        ),
    )
    context.evaluation_set = EvaluationSet(
        id="test-set",
        name="Test Eval Set",
        evaluations=eval_items,
    )
    context.evaluators = evaluators

    for key, value in context_kwargs.items():
        setattr(context, key, value)

    runtime = UiPathEvalRuntime(
        context=context,
        factory=mock_factory,
        trace_manager=mock_trace_manager,
        event_bus=mock_event_bus,
    )

    with patch.object(
        runtime,
        "execute_runtime",
        new=AsyncMock(return_value=execution_output or make_mock_execution_output()),
    ):
        await runtime.execute()

    return tracer, runtime


# --- Test classes ---


class TestEvalSetRunSpan:
    """Tests for the top-level 'Evaluation Set Run' span produced by execute()."""

    @pytest.mark.asyncio
    async def test_span_created_with_correct_name_and_type(self) -> None:
        evaluator = make_evaluator(score=0.9)
        item = make_eval_item(evaluation_criterias={"mock-evaluator": {}})
        tracer, _ = await run_evaluation([item], [evaluator])

        spans = tracer.get_spans_by_type("eval_set_run")
        assert len(spans) == 1
        assert spans[0].name == "Evaluation Set Run"
        assert spans[0].attributes["uipath.custom_instrumentation"] is True

    @pytest.mark.asyncio
    async def test_aggregate_scores_from_multiple_items(self) -> None:
        """Scores are averaged across all eval items and written to the span."""
        evaluator = make_evaluator(score=0.8)
        items = [
            make_eval_item(
                item_id="calculator-addition",
                name="Calculator addition test",
                evaluation_criterias={"mock-evaluator": {}},
            ),
            make_eval_item(
                item_id="calculator-subtraction",
                name="Calculator subtraction test",
                evaluation_criterias={"mock-evaluator": {}},
            ),
        ]
        tracer, _ = await run_evaluation(items, [evaluator])

        span = tracer.get_spans_by_type("eval_set_run")[0]
        output = json.loads(span.attributes["output"])
        assert output["scores"]["MockEvaluator"] == 80.0  # 0.8 -> 80.0

    @pytest.mark.asyncio
    async def test_metadata_attributes(self) -> None:
        evaluator = make_evaluator(score=1.0)
        item = make_eval_item(evaluation_criterias={"mock-evaluator": {}})
        tracer, _ = await run_evaluation(
            [item], [evaluator], execution_id="eval-set-run-exec-123"
        )

        span = tracer.get_spans_by_type("eval_set_run")[0]
        assert span.attributes["agentId"] == "eval-set-run-exec-123"
        assert span.attributes["agentName"] == "N/A"

        input_schema = json.loads(span.attributes["inputSchema"])
        assert input_schema["type"] == "object"
        assert "x" in input_schema["properties"]

        output_schema = json.loads(span.attributes["outputSchema"])
        assert output_schema["type"] == "object"

    @pytest.mark.asyncio
    async def test_span_has_ok_status_on_success(self) -> None:
        from opentelemetry.trace import StatusCode

        evaluator = make_evaluator(score=0.9)
        item = make_eval_item(evaluation_criterias={"mock-evaluator": {}})
        tracer, _ = await run_evaluation([item], [evaluator])

        span = tracer.get_spans_by_type("eval_set_run")[0]
        assert span._status is not None
        assert span._status.status_code == StatusCode.OK

    @pytest.mark.asyncio
    async def test_eval_set_run_id_included_when_provided(self) -> None:
        evaluator = make_evaluator(score=0.9)
        item = make_eval_item(evaluation_criterias={"mock-evaluator": {}})
        tracer, _ = await run_evaluation(
            [item], [evaluator], eval_set_run_id="run-2024-04-14-001"
        )

        span = tracer.get_spans_by_type("eval_set_run")[0]
        assert span.attributes["eval_set_run_id"] == "run-2024-04-14-001"

    @pytest.mark.asyncio
    async def test_eval_set_run_id_excluded_when_not_provided(self) -> None:
        evaluator = make_evaluator(score=0.9)
        item = make_eval_item(evaluation_criterias={"mock-evaluator": {}})
        tracer, _ = await run_evaluation([item], [evaluator])

        span = tracer.get_spans_by_type("eval_set_run")[0]
        assert "eval_set_run_id" not in span.attributes


class TestEvaluationSpan:
    """Tests for the 'Evaluation' span — one per eval item."""

    @pytest.mark.asyncio
    async def test_one_span_per_eval_item(self) -> None:
        evaluator = make_evaluator(score=0.9)
        items = [
            make_eval_item(
                item_id="greeting-english",
                name="English greeting test",
                evaluation_criterias={"mock-evaluator": {}},
            ),
            make_eval_item(
                item_id="greeting-spanish",
                name="Spanish greeting test",
                evaluation_criterias={"mock-evaluator": {}},
            ),
        ]
        tracer, _ = await run_evaluation(items, [evaluator])

        spans = tracer.get_spans_by_type("evaluation")
        assert len(spans) == 2

    @pytest.mark.asyncio
    async def test_span_has_eval_item_attributes(self) -> None:
        evaluator = make_evaluator(score=0.9)
        item = make_eval_item(
            item_id="sentiment-positive-review",
            name="Positive review sentiment check",
            evaluation_criterias={"mock-evaluator": {}},
        )
        tracer, _ = await run_evaluation([item], [evaluator])

        span = tracer.get_spans_by_type("evaluation")[0]
        assert span.attributes["eval_item_id"] == "sentiment-positive-review"
        assert span.attributes["eval_item_name"] == "Positive review sentiment check"
        assert span.attributes["execution.id"] == "sentiment-positive-review"
        assert span.attributes["uipath.custom_instrumentation"] is True

    @pytest.mark.asyncio
    async def test_span_configured_with_per_item_scores(self) -> None:
        evaluator = make_evaluator(score=0.85)
        item = make_eval_item(evaluation_criterias={"mock-evaluator": {}})
        tracer, _ = await run_evaluation([item], [evaluator])

        span = tracer.get_spans_by_type("evaluation")[0]
        output = json.loads(span.attributes["output"])
        assert "scores" in output
        assert "MockEvaluator" in output["scores"]

    @pytest.mark.asyncio
    async def test_span_has_metadata(self) -> None:
        evaluator = make_evaluator(score=0.9)
        item = make_eval_item(
            item_id="capital-city-query",
            inputs={"query": "What is the capital of France?"},
            evaluation_criterias={"mock-evaluator": {}},
        )
        tracer, _ = await run_evaluation([item], [evaluator])

        span = tracer.get_spans_by_type("evaluation")[0]
        # agentId is set to the eval item's execution_id (== str(eval_item.id))
        assert span.attributes["agentId"] == "capital-city-query"
        assert span.attributes["agentName"] == "N/A"

    @pytest.mark.asyncio
    async def test_span_has_input_data(self) -> None:
        """The evaluation span carries the eval item's inputs as serialized JSON."""
        evaluator = make_evaluator(score=0.9)
        item = make_eval_item(
            inputs={"query": "Summarize this document", "max_tokens": 100},
            evaluation_criterias={"mock-evaluator": {}},
        )
        tracer, _ = await run_evaluation([item], [evaluator])

        span = tracer.get_spans_by_type("evaluation")[0]
        assert "input" in span.attributes
        input_data = json.loads(span.attributes["input"])
        assert input_data["query"] == "Summarize this document"
        assert input_data["max_tokens"] == 100

    @pytest.mark.asyncio
    async def test_span_has_error_status_when_agent_fails(self) -> None:
        """When the agent returns an error, the evaluation span gets ERROR status."""
        from opentelemetry.trace import StatusCode

        evaluator = make_evaluator(score=0.0)
        item = make_eval_item(evaluation_criterias={"mock-evaluator": {}})
        error_output = make_mock_execution_output(
            error="Agent failed: connection timeout",
        )
        tracer, _ = await run_evaluation(
            [item], [evaluator], execution_output=error_output
        )

        span = tracer.get_spans_by_type("evaluation")[0]
        assert span._status is not None
        assert span._status.status_code == StatusCode.ERROR

    @pytest.mark.asyncio
    async def test_span_has_ok_status_on_success(self) -> None:
        """When the agent succeeds, the evaluation span gets OK status."""
        from opentelemetry.trace import StatusCode

        evaluator = make_evaluator(score=0.9)
        item = make_eval_item(evaluation_criterias={"mock-evaluator": {}})
        tracer, _ = await run_evaluation([item], [evaluator])

        span = tracer.get_spans_by_type("evaluation")[0]
        assert span._status is not None
        assert span._status.status_code == StatusCode.OK


class TestEvaluatorSpan:
    """Tests for the 'Evaluator: {name}' span — one per evaluator per item."""

    @pytest.mark.asyncio
    async def test_span_has_correct_name_and_attributes(self) -> None:
        evaluator = make_evaluator(score=0.9)
        item = make_eval_item(
            item_id="multi-step-tool-use",
            name="Multi-step tool use test case",
            evaluation_criterias={"mock-evaluator": {}},
        )
        tracer, _ = await run_evaluation([item], [evaluator])

        spans = tracer.get_spans_by_type("evaluator")
        assert len(spans) == 1
        span = spans[0]
        assert span.name == "Evaluator: MockEvaluator"
        assert span.attributes["evaluator_id"] == "mock-evaluator"
        assert span.attributes["evaluator_name"] == "MockEvaluator"
        assert span.attributes["eval_item_id"] == "multi-step-tool-use"
        assert span.attributes["uipath.custom_instrumentation"] is True

    @pytest.mark.asyncio
    async def test_multiple_evaluators_produce_multiple_spans(self) -> None:
        evaluators = [
            make_evaluator(
                name="MockEvaluatorA", evaluator_id="mock-evaluator-a", score=0.9
            ),
            make_evaluator(
                name="MockEvaluatorB", evaluator_id="mock-evaluator-b", score=0.8
            ),
            make_evaluator(
                name="MockEvaluatorC", evaluator_id="mock-evaluator-c", score=0.7
            ),
        ]
        item = make_eval_item(
            evaluation_criterias={
                "mock-evaluator-a": {},
                "mock-evaluator-b": {},
                "mock-evaluator-c": {},
            }
        )
        tracer, _ = await run_evaluation([item], evaluators)

        spans = tracer.get_spans_by_type("evaluator")
        assert len(spans) == 3
        span_names = {s.name for s in spans}
        assert span_names == {
            "Evaluator: MockEvaluatorA",
            "Evaluator: MockEvaluatorB",
            "Evaluator: MockEvaluatorC",
        }

    @pytest.mark.asyncio
    async def test_multiple_items_each_get_evaluator_spans(self) -> None:
        evaluator = make_evaluator(score=0.9)
        items = [
            make_eval_item(
                item_id="invoice-extraction",
                name="Invoice data extraction",
                evaluation_criterias={"mock-evaluator": {}},
            ),
            make_eval_item(
                item_id="receipt-extraction",
                name="Receipt data extraction",
                evaluation_criterias={"mock-evaluator": {}},
            ),
        ]
        tracer, _ = await run_evaluation(items, [evaluator])

        spans = tracer.get_spans_by_type("evaluator")
        assert len(spans) == 2
        item_ids = {s.attributes["eval_item_id"] for s in spans}
        assert item_ids == {"invoice-extraction", "receipt-extraction"}


class TestEvaluationOutputSpan:
    """Tests for the 'Evaluation output' span — the evaluator's score."""

    @pytest.mark.asyncio
    async def test_span_created_with_correct_attributes(self) -> None:
        evaluator = make_evaluator(score=0.75)
        item = make_eval_item(evaluation_criterias={"mock-evaluator": {}})
        tracer, _ = await run_evaluation([item], [evaluator])

        output_spans = tracer.get_spans_by_attr("span.type", "evalOutput")
        assert len(output_spans) == 1
        span = output_spans[0]
        assert span.name == "Evaluation output"
        assert span.attributes["value"] == 0.75
        assert span.attributes["evaluatorId"] == "mock-evaluator"
        assert span.attributes["openinference.span.kind"] == "CHAIN"
        assert span.attributes["uipath.custom_instrumentation"] is True

    @pytest.mark.asyncio
    async def test_output_json_has_normalized_score_and_type(self) -> None:
        evaluator = make_evaluator(score=0.85)
        item = make_eval_item(evaluation_criterias={"mock-evaluator": {}})
        tracer, _ = await run_evaluation([item], [evaluator])

        span = tracer.get_spans_by_attr("span.type", "evalOutput")[0]
        output = json.loads(span.attributes["output"])
        assert output["type"] == 1
        assert output["score"] == 85.0  # 0.85 normalized to 0-100
        assert output["evaluatorId"] == "mock-evaluator"

    @pytest.mark.asyncio
    async def test_justification_from_pydantic_details(self) -> None:
        class MockEvaluatorDetails(BaseModel):
            justification: str
            similarity_score: float = 0.0

        details = MockEvaluatorDetails(
            justification="Agent output is semantically equivalent to expected output",
            similarity_score=0.92,
        )
        evaluator = make_evaluator(score=0.92, details=details)
        item = make_eval_item(evaluation_criterias={"mock-evaluator": {}})
        tracer, _ = await run_evaluation([item], [evaluator])

        span = tracer.get_spans_by_attr("span.type", "evalOutput")[0]
        assert (
            span.attributes["justification"]
            == "Agent output is semantically equivalent to expected output"
        )
        # justification also appears in the output JSON
        output = json.loads(span.attributes["output"])
        assert (
            output["justification"]
            == "Agent output is semantically equivalent to expected output"
        )

    @pytest.mark.asyncio
    async def test_justification_from_string_details(self) -> None:
        evaluator = make_evaluator(
            score=0.8,
            details="Output correctly classified as positive sentiment",
        )
        item = make_eval_item(evaluation_criterias={"mock-evaluator": {}})
        tracer, _ = await run_evaluation([item], [evaluator])

        span = tracer.get_spans_by_attr("span.type", "evalOutput")[0]
        assert (
            span.attributes["justification"]
            == "Output correctly classified as positive sentiment"
        )

    @pytest.mark.asyncio
    async def test_no_justification_when_no_details(self) -> None:
        evaluator = make_evaluator(score=1.0, details=None)
        item = make_eval_item(evaluation_criterias={"mock-evaluator": {}})
        tracer, _ = await run_evaluation([item], [evaluator])

        span = tracer.get_spans_by_attr("span.type", "evalOutput")[0]
        assert "justification" not in span.attributes
        # justification also absent from output JSON (exclude_none=True)
        output = json.loads(span.attributes["output"])
        assert "justification" not in output


class TestSpanHierarchy:
    """Tests that the full span tree is produced in the correct structure."""

    @pytest.mark.asyncio
    async def test_full_span_tree(self) -> None:
        """One item + one evaluator produces all four span types."""
        evaluator = make_evaluator(score=0.95)
        item = make_eval_item(
            item_id="booking-flow-happy-path",
            name="Booking flow happy path",
            evaluation_criterias={"mock-evaluator": {}},
        )
        tracer, _ = await run_evaluation([item], [evaluator])

        assert len(tracer.get_spans_by_type("eval_set_run")) == 1
        assert len(tracer.get_spans_by_type("evaluation")) == 1
        assert len(tracer.get_spans_by_type("evaluator")) == 1
        assert len(tracer.get_spans_by_attr("span.type", "evalOutput")) == 1

    @pytest.mark.asyncio
    async def test_span_ordering(self) -> None:
        """Spans are created in the correct order: parent before child."""
        evaluator = make_evaluator(score=0.9)
        item = make_eval_item(evaluation_criterias={"mock-evaluator": {}})
        tracer, _ = await run_evaluation([item], [evaluator])

        names = [s.name for s in tracer.captured_spans]
        assert names.index("Evaluation Set Run") < names.index("Evaluation")
        assert names.index("Evaluation") < names.index(
            "Evaluator: MockEvaluator"
        )
        assert names.index("Evaluator: MockEvaluator") < names.index(
            "Evaluation output"
        )

    @pytest.mark.asyncio
    async def test_multiple_items_and_evaluators(self) -> None:
        """Two items x two evaluators produces the expected span counts."""
        evaluators = [
            make_evaluator(
                name="MockEvaluatorA", evaluator_id="mock-evaluator-a", score=0.9
            ),
            make_evaluator(
                name="MockEvaluatorB", evaluator_id="mock-evaluator-b", score=0.8
            ),
        ]
        items = [
            make_eval_item(
                item_id="api-response-format",
                name="API response format validation",
                evaluation_criterias={
                    "mock-evaluator-a": {},
                    "mock-evaluator-b": {},
                },
            ),
            make_eval_item(
                item_id="error-handling-graceful",
                name="Graceful error handling check",
                evaluation_criterias={
                    "mock-evaluator-a": {},
                    "mock-evaluator-b": {},
                },
            ),
        ]
        tracer, _ = await run_evaluation(items, evaluators)

        assert len(tracer.get_spans_by_type("eval_set_run")) == 1
        assert len(tracer.get_spans_by_type("evaluation")) == 2
        assert len(tracer.get_spans_by_type("evaluator")) == 4  # 2 items x 2 evaluators
        assert len(tracer.get_spans_by_attr("span.type", "evalOutput")) == 4
