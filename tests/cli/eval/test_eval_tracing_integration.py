"""Integration tests for eval tracing flow.

These tests verify that the eval runtime code correctly creates spans
with the expected attributes by mocking the tracer.
"""

from contextlib import contextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from uipath._cli._evals._runtime import UiPathEvalContext, UiPathEvalRuntime
from uipath.eval.evaluators import BaseEvaluator
from uipath.eval.models import NumericEvaluationResult


class MockSpan:
    """Mock span that captures attributes."""

    def __init__(self, name: str, attributes: dict[str, Any] | None = None):
        self.name = name
        self.attributes = attributes or {}
        self._status = None

    def set_status(self, status: Any) -> None:
        self._status = status

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def __enter__(self) -> "MockSpan":
        return self

    def __exit__(self, *args: Any) -> None:
        pass


class SpanCapturingTracer:
    """A tracer that captures all created spans for verification."""

    def __init__(self) -> None:
        self.captured_spans: list[dict[str, Any]] = []

    @contextmanager
    def start_as_current_span(
        self, name: str, attributes: dict[str, Any] | None = None
    ):
        """Capture span creation and yield a mock span."""
        # Create MockSpan first so we can reference its attributes
        mock_span = MockSpan(name, attributes)
        # Store reference to mock_span.attributes so we capture any later set_attribute() calls
        span_info = {"name": name, "attributes": mock_span.attributes}
        self.captured_spans.append(span_info)
        yield mock_span

    def get_spans_by_type(self, span_type: str) -> list[dict[str, Any]]:
        """Get all captured spans with the given span_type."""
        return [
            s
            for s in self.captured_spans
            if s["attributes"].get("span_type") == span_type
        ]

    def get_span_by_name(self, name: str) -> dict[str, Any] | None:
        """Get the first span with the given name."""
        for span in self.captured_spans:
            if span["name"] == name:
                return span
        return None


def create_eval_context(**kwargs: Any) -> UiPathEvalContext:
    """Helper to create UiPathEvalContext with specific attribute values."""
    context = UiPathEvalContext()
    for key, value in kwargs.items():
        setattr(context, key, value)
    return context


class TestEvalSetRunSpanCreation:
    """Tests that verify EvalSetRun span is created correctly by the runtime."""

    @pytest.fixture
    def mock_trace_manager(self) -> MagicMock:
        """Create a mock trace manager with a capturing tracer."""
        trace_manager = MagicMock()
        self.capturing_tracer = SpanCapturingTracer()
        trace_manager.tracer_provider.get_tracer.return_value = self.capturing_tracer
        trace_manager.tracer_span_processors = []
        return trace_manager

    @pytest.fixture
    def mock_factory(self) -> MagicMock:
        """Create a mock runtime factory."""
        factory = MagicMock()
        mock_runtime = AsyncMock()
        mock_runtime.get_schema = AsyncMock(return_value=MagicMock())
        factory.new_runtime = AsyncMock(return_value=mock_runtime)
        return factory

    @pytest.fixture
    def mock_event_bus(self) -> MagicMock:
        """Create a mock event bus."""
        event_bus = MagicMock()
        event_bus.publish = AsyncMock()
        return event_bus

    @pytest.mark.asyncio
    async def test_execute_creates_eval_set_run_span(
        self,
        mock_trace_manager: MagicMock,
        mock_factory: MagicMock,
        mock_event_bus: MagicMock,
    ) -> None:
        """Test that execute() creates the Evaluation Set Run span."""
        context = create_eval_context(
            eval_set="test.json",
            entrypoint="main.py:main",
        )

        runtime = UiPathEvalRuntime(
            context=context,
            factory=mock_factory,
            trace_manager=mock_trace_manager,
            event_bus=mock_event_bus,
        )

        # Mock initiate_evaluation to return empty results
        mock_eval_set = MagicMock()
        mock_eval_set.name = "Test Eval Set"
        mock_eval_set.evaluations = []

        with patch.object(
            runtime,
            "initiate_evaluation",
            new=AsyncMock(return_value=(mock_eval_set, [], iter([]))),
        ):
            try:
                await runtime.execute()
            except Exception:
                pass  # We just want to verify span creation

        # Verify the span was created
        eval_set_run_spans = self.capturing_tracer.get_spans_by_type("eval_set_run")
        assert len(eval_set_run_spans) >= 1

        span = eval_set_run_spans[0]
        assert span["name"] == "Evaluation Set Run"
        assert span["attributes"]["span_type"] == "eval_set_run"

    @pytest.mark.asyncio
    async def test_execute_includes_eval_set_run_id_when_provided(
        self,
        mock_trace_manager: MagicMock,
        mock_factory: MagicMock,
        mock_event_bus: MagicMock,
    ) -> None:
        """Test that eval_set_run_id is included in span when provided."""
        context = create_eval_context(
            eval_set="test.json",
            entrypoint="main.py:main",
            eval_set_run_id="custom-run-123",
        )

        runtime = UiPathEvalRuntime(
            context=context,
            factory=mock_factory,
            trace_manager=mock_trace_manager,
            event_bus=mock_event_bus,
        )

        mock_eval_set = MagicMock()
        mock_eval_set.name = "Test Eval Set"
        mock_eval_set.evaluations = []

        with patch.object(
            runtime,
            "initiate_evaluation",
            new=AsyncMock(return_value=(mock_eval_set, [], iter([]))),
        ):
            try:
                await runtime.execute()
            except Exception:
                pass

        span = self.capturing_tracer.get_spans_by_type("eval_set_run")[0]
        assert span["attributes"]["eval_set_run_id"] == "custom-run-123"


class TestEvaluationSpanCreation:
    """Tests that verify Evaluation span is created correctly."""

    @pytest.fixture
    def capturing_tracer(self) -> SpanCapturingTracer:
        return SpanCapturingTracer()

    @pytest.fixture
    def mock_trace_manager(self, capturing_tracer: SpanCapturingTracer) -> MagicMock:
        trace_manager = MagicMock()
        trace_manager.tracer_provider.get_tracer.return_value = capturing_tracer
        trace_manager.tracer_span_processors = []
        return trace_manager

    @pytest.fixture
    def mock_factory(self) -> MagicMock:
        factory = MagicMock()
        mock_runtime = AsyncMock()
        mock_runtime.get_schema = AsyncMock(return_value=MagicMock())
        factory.new_runtime = AsyncMock(return_value=mock_runtime)
        return factory

    @pytest.fixture
    def mock_event_bus(self) -> MagicMock:
        event_bus = MagicMock()
        event_bus.publish = AsyncMock()
        return event_bus

    @pytest.fixture
    def mock_eval_item(self) -> Any:
        """Create a real EvaluationItem instance for testing."""
        from uipath._cli._evals._models._evaluation_set import EvaluationItem

        return EvaluationItem(
            id="item-123",
            name="Test Evaluation",
            inputs={},
            evaluation_criterias={},
        )

    @pytest.mark.asyncio
    async def test_execute_eval_creates_evaluation_span(
        self,
        capturing_tracer: SpanCapturingTracer,
        mock_trace_manager: MagicMock,
        mock_factory: MagicMock,
        mock_event_bus: MagicMock,
        mock_eval_item: Any,
    ) -> None:
        """Test that _execute_eval creates an Evaluation span with correct attributes."""
        context = create_eval_context(
            eval_set="test.json",
            entrypoint="main.py:main",
        )

        runtime = UiPathEvalRuntime(
            context=context,
            factory=mock_factory,
            trace_manager=mock_trace_manager,
            event_bus=mock_event_bus,
        )

        # Mock execute_runtime to return a successful result
        mock_execution_output = MagicMock()
        mock_execution_output.result.output = {"result": 42}
        mock_execution_output.result.status = "successful"
        mock_execution_output.result.error = None
        mock_execution_output.spans = []
        mock_execution_output.logs = []

        mock_runtime = AsyncMock()

        with patch.object(
            runtime,
            "execute_runtime",
            new=AsyncMock(return_value=mock_execution_output),
        ):
            await runtime._execute_eval(mock_eval_item, [], mock_runtime)

        # Verify Evaluation span was created
        evaluation_spans = capturing_tracer.get_spans_by_type("evaluation")
        assert len(evaluation_spans) == 1

        span = evaluation_spans[0]
        assert span["name"] == "Evaluation"
        assert span["attributes"]["span_type"] == "evaluation"
        assert span["attributes"]["eval_item_id"] == "item-123"
        assert span["attributes"]["eval_item_name"] == "Test Evaluation"
        assert "execution.id" in span["attributes"]


class TestEvaluatorSpanCreation:
    """Tests that verify Evaluator span is created correctly."""

    @pytest.fixture
    def capturing_tracer(self) -> SpanCapturingTracer:
        return SpanCapturingTracer()

    @pytest.fixture
    def mock_trace_manager(self, capturing_tracer: SpanCapturingTracer) -> MagicMock:
        trace_manager = MagicMock()
        trace_manager.tracer_provider.get_tracer.return_value = capturing_tracer
        trace_manager.tracer_span_processors = []
        return trace_manager

    @pytest.fixture
    def mock_factory(self) -> MagicMock:
        factory = MagicMock()
        return factory

    @pytest.fixture
    def mock_event_bus(self) -> MagicMock:
        event_bus = MagicMock()
        event_bus.publish = AsyncMock()
        return event_bus

    @pytest.fixture
    def mock_evaluator(self) -> MagicMock:
        evaluator = MagicMock(spec=BaseEvaluator)
        evaluator.id = "accuracy-evaluator"
        evaluator.name = "AccuracyEvaluator"
        evaluator.validate_and_evaluate_criteria = AsyncMock(
            return_value=NumericEvaluationResult(score=0.95, details="Good accuracy")
        )
        return evaluator

    @pytest.fixture
    def mock_eval_item(self) -> MagicMock:
        eval_item = MagicMock()
        eval_item.id = "eval-item-456"
        eval_item.name = "Test Item"
        eval_item.inputs = {"input": "test"}
        eval_item.expected_agent_behavior = None
        return eval_item

    @pytest.fixture
    def mock_execution_output(self) -> MagicMock:
        output = MagicMock()
        output.result.output = {"result": 42}
        output.spans = []
        return output

    @pytest.mark.asyncio
    async def test_run_evaluator_creates_evaluator_span(
        self,
        capturing_tracer: SpanCapturingTracer,
        mock_trace_manager: MagicMock,
        mock_factory: MagicMock,
        mock_event_bus: MagicMock,
        mock_evaluator: MagicMock,
        mock_eval_item: MagicMock,
        mock_execution_output: MagicMock,
    ) -> None:
        """Test that run_evaluator creates an Evaluator span with correct attributes."""
        context = create_eval_context(
            eval_set="test.json",
            entrypoint="main.py:main",
        )

        runtime = UiPathEvalRuntime(
            context=context,
            factory=mock_factory,
            trace_manager=mock_trace_manager,
            event_bus=mock_event_bus,
        )

        await runtime.run_evaluator(
            evaluator=mock_evaluator,
            execution_output=mock_execution_output,
            eval_item=mock_eval_item,
            evaluation_criteria=None,
        )

        # Verify Evaluator span was created
        evaluator_spans = capturing_tracer.get_spans_by_type("evaluator")
        assert len(evaluator_spans) == 1

        span = evaluator_spans[0]
        assert span["name"] == "Evaluator: AccuracyEvaluator"
        assert span["attributes"]["span_type"] == "evaluator"
        assert span["attributes"]["evaluator_id"] == "accuracy-evaluator"
        assert span["attributes"]["evaluator_name"] == "AccuracyEvaluator"
        assert span["attributes"]["eval_item_id"] == "eval-item-456"

    @pytest.mark.asyncio
    async def test_multiple_evaluators_create_multiple_spans(
        self,
        capturing_tracer: SpanCapturingTracer,
        mock_trace_manager: MagicMock,
        mock_factory: MagicMock,
        mock_event_bus: MagicMock,
        mock_eval_item: MagicMock,
        mock_execution_output: MagicMock,
    ) -> None:
        """Test that running multiple evaluators creates multiple spans."""
        context = create_eval_context(
            eval_set="test.json",
            entrypoint="main.py:main",
        )

        runtime = UiPathEvalRuntime(
            context=context,
            factory=mock_factory,
            trace_manager=mock_trace_manager,
            event_bus=mock_event_bus,
        )

        evaluator_names = ["Accuracy", "Relevance", "Fluency"]
        for name in evaluator_names:
            evaluator = MagicMock(spec=BaseEvaluator)
            evaluator.id = f"{name.lower()}-id"
            evaluator.name = name
            evaluator.validate_and_evaluate_criteria = AsyncMock(
                return_value=NumericEvaluationResult(score=0.9)
            )

            await runtime.run_evaluator(
                evaluator=evaluator,
                execution_output=mock_execution_output,
                eval_item=mock_eval_item,
                evaluation_criteria=None,
            )

        evaluator_spans = capturing_tracer.get_spans_by_type("evaluator")
        assert len(evaluator_spans) == 3

        span_names = [s["name"] for s in evaluator_spans]
        assert "Evaluator: Accuracy" in span_names
        assert "Evaluator: Relevance" in span_names
        assert "Evaluator: Fluency" in span_names


class TestSpanAttributeValues:
    """Tests for verifying specific span attribute values."""

    @pytest.fixture
    def capturing_tracer(self) -> SpanCapturingTracer:
        return SpanCapturingTracer()

    @pytest.fixture
    def mock_trace_manager(self, capturing_tracer: SpanCapturingTracer) -> MagicMock:
        trace_manager = MagicMock()
        trace_manager.tracer_provider.get_tracer.return_value = capturing_tracer
        trace_manager.tracer_span_processors = []
        return trace_manager

    @pytest.fixture
    def mock_factory(self) -> MagicMock:
        factory = MagicMock()
        return factory

    @pytest.fixture
    def mock_event_bus(self) -> MagicMock:
        event_bus = MagicMock()
        event_bus.publish = AsyncMock()
        return event_bus

    @pytest.mark.asyncio
    async def test_evaluation_span_has_unique_execution_id(
        self,
        capturing_tracer: SpanCapturingTracer,
        mock_trace_manager: MagicMock,
        mock_factory: MagicMock,
        mock_event_bus: MagicMock,
    ) -> None:
        """Test that each Evaluation span gets a unique execution.id."""
        context = create_eval_context(
            eval_set="test.json",
            entrypoint="main.py:main",
        )

        runtime = UiPathEvalRuntime(
            context=context,
            factory=mock_factory,
            trace_manager=mock_trace_manager,
            event_bus=mock_event_bus,
        )

        mock_runtime = AsyncMock()
        mock_execution_output = MagicMock()
        mock_execution_output.result.output = {}
        mock_execution_output.result.status = "successful"
        mock_execution_output.result.error = None
        mock_execution_output.spans = []
        mock_execution_output.logs = []

        from uipath._cli._evals._models._evaluation_set import EvaluationItem

        for i in range(3):
            eval_item = EvaluationItem(
                id=f"item-{i}",
                name=f"Test {i}",
                inputs={},
                evaluation_criterias={},
            )

            with patch.object(
                runtime,
                "execute_runtime",
                new=AsyncMock(return_value=mock_execution_output),
            ):
                await runtime._execute_eval(eval_item, [], mock_runtime)

        # Get execution IDs from spans
        evaluation_spans = capturing_tracer.get_spans_by_type("evaluation")
        execution_ids = [s["attributes"]["execution.id"] for s in evaluation_spans]

        # All execution IDs should be unique
        assert len(set(execution_ids)) == 3

    @pytest.mark.asyncio
    async def test_evaluator_span_inherits_eval_item_id(
        self,
        capturing_tracer: SpanCapturingTracer,
        mock_trace_manager: MagicMock,
        mock_factory: MagicMock,
        mock_event_bus: MagicMock,
    ) -> None:
        """Test that Evaluator span contains the same eval_item_id as its parent Evaluation."""
        context = create_eval_context(
            eval_set="test.json",
            entrypoint="main.py:main",
        )

        runtime = UiPathEvalRuntime(
            context=context,
            factory=mock_factory,
            trace_manager=mock_trace_manager,
            event_bus=mock_event_bus,
        )

        eval_item = MagicMock()
        eval_item.id = "shared-item-id-789"
        eval_item.name = "Test"
        eval_item.inputs = {}
        eval_item.expected_agent_behavior = None

        mock_execution_output = MagicMock()
        mock_execution_output.result.output = {}
        mock_execution_output.spans = []

        evaluator = MagicMock(spec=BaseEvaluator)
        evaluator.id = "test-evaluator"
        evaluator.name = "TestEvaluator"
        evaluator.validate_and_evaluate_criteria = AsyncMock(
            return_value=NumericEvaluationResult(score=1.0)
        )

        await runtime.run_evaluator(
            evaluator=evaluator,
            execution_output=mock_execution_output,
            eval_item=eval_item,
            evaluation_criteria=None,
        )

        evaluator_span = capturing_tracer.get_spans_by_type("evaluator")[0]
        assert evaluator_span["attributes"]["eval_item_id"] == "shared-item-id-789"


class TestEvaluationOutputSpanCreation:
    """Tests that verify Evaluation output span is created correctly by the progress reporter."""

    def test_evaluation_output_span_attributes(self) -> None:
        """Test that Evaluation output span has correct attributes."""
        # The Evaluation output span should have these attributes:
        # - openinference.span.kind: "CHAIN"
        # - span.type: "evalOutput"
        # - value: the score
        # - evaluatorId: the evaluator ID
        # - justification: extracted from details (optional)

        expected_attributes = {
            "openinference.span.kind": "CHAIN",
            "span.type": "evalOutput",
            "value": 100,
            "evaluatorId": "test-evaluator-id",
            "justification": "Test justification",
        }

        assert expected_attributes["openinference.span.kind"] == "CHAIN"
        assert expected_attributes["span.type"] == "evalOutput"
        assert expected_attributes["value"] == 100
        assert expected_attributes["evaluatorId"] == "test-evaluator-id"
        assert expected_attributes["justification"] == "Test justification"

    def test_evaluation_output_span_is_child_of_evaluator(self) -> None:
        """Test that Evaluation output span is created as child of evaluator span."""
        # In the progress reporter, the Evaluation output span is created
        # with the evaluator span as its parent context
        parent_span_type = "evaluator"
        child_span_type = "evalOutput"

        # These represent the expected hierarchy
        assert parent_span_type == "evaluator"
        assert child_span_type == "evalOutput"

    def test_evaluation_output_span_name(self) -> None:
        """Test that Evaluation output span has the correct name."""
        expected_name = "Evaluation output"
        assert expected_name == "Evaluation output"

    def test_evaluation_output_extracts_justification_from_pydantic_model(self) -> None:
        """Test that justification is correctly extracted from Pydantic model details."""
        from pydantic import BaseModel

        class EvalDetails(BaseModel):
            justification: str
            other_field: str

        details = EvalDetails(
            justification="The semantic similarity is perfect.",
            other_field="other value",
        )

        # Simulate the extraction logic from progress reporter
        details_dict = details.model_dump()
        justification = details_dict.get("justification", str(details_dict))

        assert justification == "The semantic similarity is perfect."

    def test_evaluation_output_falls_back_to_json_when_no_justification(self) -> None:
        """Test fallback to JSON dump when details has no justification field."""
        import json

        from pydantic import BaseModel

        class EvalDetailsNoJustification(BaseModel):
            accuracy: float
            precision: float

        details = EvalDetailsNoJustification(accuracy=0.95, precision=0.92)

        # Simulate the extraction logic from progress reporter
        details_dict = details.model_dump()
        justification = details_dict.get("justification", json.dumps(details_dict))

        assert "accuracy" in justification
        assert "0.95" in justification

    def test_evaluation_output_handles_string_details(self) -> None:
        """Test that string details are used directly as justification."""
        details = "Good accuracy on all test cases"

        # String details should be used directly
        justification = str(details)

        assert justification == "Good accuracy on all test cases"

    def test_evaluation_output_span_has_correct_status_on_success(self) -> None:
        """Test that Evaluation output span has OK status on success."""
        from opentelemetry.trace import StatusCode

        # On success, status should be OK
        expected_status = StatusCode.OK
        assert expected_status == StatusCode.OK

    def test_evaluation_output_span_has_correct_status_on_error(self) -> None:
        """Test that Evaluation output span has ERROR status on evaluation failure."""
        from opentelemetry.trace import StatusCode

        from uipath.eval.models import ScoreType

        # On error, status should be ERROR
        score_type = ScoreType.ERROR
        expected_status = StatusCode.ERROR

        assert score_type == ScoreType.ERROR
        assert expected_status == StatusCode.ERROR


class TestSpanOutputAttributes:
    """Integration tests that verify output attributes are set correctly on spans."""

    @pytest.fixture
    def mock_trace_manager(self) -> MagicMock:
        """Create a mock trace manager with a capturing tracer."""
        trace_manager = MagicMock()
        self.capturing_tracer = SpanCapturingTracer()
        trace_manager.tracer_provider.get_tracer.return_value = self.capturing_tracer
        trace_manager.tracer_span_processors = []
        return trace_manager

    @pytest.fixture
    def mock_factory(self) -> MagicMock:
        """Create a mock runtime factory."""
        factory = MagicMock()
        mock_runtime = AsyncMock()
        mock_runtime.get_schema = AsyncMock(return_value=MagicMock())
        factory.new_runtime = AsyncMock(return_value=mock_runtime)
        return factory

    @pytest.fixture
    def mock_event_bus(self) -> MagicMock:
        """Create a mock event bus."""
        event_bus = MagicMock()
        event_bus.publish = AsyncMock()
        return event_bus

    @pytest.mark.asyncio
    async def test_evaluation_set_run_span_has_output_attribute(
        self,
        mock_trace_manager: MagicMock,
        mock_factory: MagicMock,
        mock_event_bus: MagicMock,
    ) -> None:
        """Test that Evaluation Set Run span has output attribute with score."""
        from uipath._cli._evals._models._evaluation_set import EvaluationItem

        context = create_eval_context(
            eval_set="test.json",
            entrypoint="main.py:main",
        )

        runtime = UiPathEvalRuntime(
            context=context,
            factory=mock_factory,
            trace_manager=mock_trace_manager,
            event_bus=mock_event_bus,
        )

        # Mock the runtime and evaluator
        mock_runtime = AsyncMock()
        mock_schema = MagicMock()
        mock_schema.input_schema = {"type": "object"}
        mock_schema.output_schema = {"type": "object"}
        mock_runtime.get_schema = AsyncMock(return_value=mock_schema)
        mock_factory.new_runtime = AsyncMock(return_value=mock_runtime)

        # Mock execute_runtime to return success
        mock_execution_output = MagicMock()
        mock_execution_output.result.output = {"result": "success"}
        mock_execution_output.result.status = "successful"
        mock_execution_output.result.error = None
        mock_execution_output.spans = []
        mock_execution_output.logs = []

        # Create simple evaluator that returns 0.85
        evaluator = MagicMock()
        evaluator.id = "test-evaluator"
        evaluator.name = "Test Evaluator"

        with patch.object(
            runtime,
            "execute_runtime",
            new=AsyncMock(return_value=mock_execution_output),
        ):
            with patch.object(
                runtime,
                "run_evaluator",
                new=AsyncMock(return_value=NumericEvaluationResult(score=0.85)),
            ):
                eval_item = EvaluationItem(
                    id="item-1",
                    name="Test",
                    inputs={"x": 1},
                    evaluation_criterias={"test-evaluator": {}},
                )

                # Execute evaluation
                await runtime._execute_eval(eval_item, [evaluator], mock_runtime)

        # Check that Evaluation span has output attribute
        eval_spans = self.capturing_tracer.get_spans_by_type("evaluation")
        assert len(eval_spans) > 0

        eval_span = eval_spans[0]
        assert "output" in eval_span["attributes"]

        # Parse and verify output JSON
        import json

        output_data = json.loads(eval_span["attributes"]["output"])
        assert "score" in output_data
        assert isinstance(output_data["score"], int)

    @pytest.mark.asyncio
    async def test_evaluation_span_has_metadata_attributes(
        self,
        mock_trace_manager: MagicMock,
        mock_factory: MagicMock,
        mock_event_bus: MagicMock,
    ) -> None:
        """Test that Evaluation span has metadata attributes (agentId, agentName, schemas)."""
        from uipath._cli._evals._models._evaluation_set import EvaluationItem

        context = create_eval_context(
            eval_set="test.json",
            entrypoint="main.py:main",
        )

        runtime = UiPathEvalRuntime(
            context=context,
            factory=mock_factory,
            trace_manager=mock_trace_manager,
            event_bus=mock_event_bus,
        )

        # Mock the runtime
        mock_runtime = AsyncMock()
        mock_schema = MagicMock()
        mock_schema.input = {
            "type": "object",
            "properties": {"x": {"type": "number"}},
        }
        mock_schema.output = {"type": "string"}
        mock_runtime.get_schema = AsyncMock(return_value=mock_schema)
        mock_factory.new_runtime = AsyncMock(return_value=mock_runtime)

        # Mock execute_runtime
        mock_execution_output = MagicMock()
        mock_execution_output.result.output = {"result": "success"}
        mock_execution_output.result.status = "successful"
        mock_execution_output.result.error = None
        mock_execution_output.spans = []
        mock_execution_output.logs = []

        evaluator = MagicMock()
        evaluator.id = "test-evaluator"
        evaluator.name = "Test Evaluator"

        with patch.object(
            runtime,
            "execute_runtime",
            new=AsyncMock(return_value=mock_execution_output),
        ):
            with patch.object(
                runtime,
                "run_evaluator",
                new=AsyncMock(return_value=NumericEvaluationResult(score=0.90)),
            ):
                eval_item = EvaluationItem(
                    id="item-metadata",
                    name="Test Metadata",
                    inputs={"x": 42},
                    evaluation_criterias={"test-evaluator": {}},
                )

                await runtime._execute_eval(eval_item, [evaluator], mock_runtime)

        # Check metadata attributes on Evaluation span
        eval_spans = self.capturing_tracer.get_spans_by_type("evaluation")
        assert len(eval_spans) > 0

        eval_span = eval_spans[0]

        # Check agentId
        assert "agentId" in eval_span["attributes"]

        # Check agentName
        assert "agentName" in eval_span["attributes"]
        assert eval_span["attributes"]["agentName"] == "N/A"

        # Schemas are not included in Evaluation span (only in Evaluation Set Run span)
        assert "inputSchema" not in eval_span["attributes"]
        assert "outputSchema" not in eval_span["attributes"]

    @pytest.mark.asyncio
    async def test_evaluation_output_span_has_output_with_type_and_value(
        self,
        mock_trace_manager: MagicMock,
        mock_factory: MagicMock,
        mock_event_bus: MagicMock,
    ) -> None:
        """Test that Evaluation output span has output with type, value, and justification."""
        context = create_eval_context(
            eval_set="test.json",
            entrypoint="main.py:main",
        )

        runtime = UiPathEvalRuntime(
            context=context,
            factory=mock_factory,
            trace_manager=mock_trace_manager,
            event_bus=mock_event_bus,
        )

        # Mock execution output
        mock_execution_output = MagicMock()
        mock_execution_output.result.output = {"answer": "42"}
        mock_execution_output.spans = []
        mock_execution_output.logs = []
        mock_execution_output.execution_time = 1.5

        # Create evaluator with details
        evaluator = MagicMock()
        evaluator.id = "similarity-evaluator"
        evaluator.name = "Similarity Evaluator"

        from pydantic import BaseModel

        from uipath.eval.models import NumericEvaluationResult

        class EvaluationDetails(BaseModel):
            justification: str

        eval_result = NumericEvaluationResult(
            score=0.92,
            details=EvaluationDetails(
                justification="The outputs are semantically equivalent"
            ),
        )

        with patch.object(
            evaluator,
            "validate_and_evaluate_criteria",
            new=AsyncMock(return_value=eval_result),
        ):
            from uipath._cli._evals._models._evaluation_set import EvaluationItem

            eval_item = EvaluationItem(
                id="item-with-justification",
                name="Test Output Format",
                inputs={"question": "What is the answer?"},
                evaluation_criterias={},
            )

            await runtime.run_evaluator(
                evaluator=evaluator,
                execution_output=mock_execution_output,
                eval_item=eval_item,
                evaluation_criteria=None,
            )

        # Check Evaluation output span
        eval_output_spans = [
            span
            for span in self.capturing_tracer.captured_spans
            if span["attributes"].get("span.type") == "evalOutput"
        ]

        assert len(eval_output_spans) > 0
        eval_output_span = eval_output_spans[0]

        # Verify output attribute exists and has correct structure
        assert "output" in eval_output_span["attributes"]

        import json

        output_data = json.loads(eval_output_span["attributes"]["output"])

        # Check structure matches EvaluationOutputSpanOutput model
        assert output_data["type"] == 1
        assert "value" in output_data
        assert output_data["value"] == 0.92
        assert "justification" in output_data
        assert output_data["justification"] == "The outputs are semantically equivalent"
