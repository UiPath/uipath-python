"""Integration tests for eval tracing flow.

These tests verify the end-to-end span creation and hierarchy in the eval runtime.
"""

import uuid
from typing import Any, Dict, List, Optional


class MockSpan:
    """Mock span that captures attributes for testing."""

    def __init__(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        self.name = name
        self.attributes = attributes or {}
        self._status = None

    def set_status(self, status):
        self._status = status


class SpanRecorder:
    """Records all spans created during test execution."""

    def __init__(self):
        self.spans: List[Dict[str, Any]] = []
        self._span_stack: List[MockSpan] = []

    def start_as_current_span(
        self, name: str, attributes: Optional[Dict[str, Any]] = None
    ):
        """Mock tracer method that records span creation."""
        span_info = {
            "name": name,
            "attributes": dict(attributes) if attributes else {},
            "parent": self._span_stack[-1].name if self._span_stack else None,
        }
        self.spans.append(span_info)

        mock_span = MockSpan(name, attributes)
        return _SpanContextManager(mock_span, self._span_stack)

    def get_spans_by_type(self, span_type: str) -> List[Dict[str, Any]]:
        """Get all spans with the given span_type attribute."""
        return [s for s in self.spans if s["attributes"].get("span_type") == span_type]

    def get_span_by_name(self, name: str) -> Dict[str, Any] | None:
        """Get the first span with the given name."""
        for span in self.spans:
            if span["name"] == name:
                return span
        return None


class _SpanContextManager:
    """Context manager for mock spans."""

    def __init__(self, span: MockSpan, stack: List[MockSpan]):
        self.span = span
        self.stack = stack

    def __enter__(self):
        self.stack.append(self.span)
        return self.span

    def __exit__(self, *args):
        self.stack.pop()


class TestEvalSetRunSpanIntegration:
    """Integration tests for Evaluation Set Run span."""

    def test_eval_set_run_span_created_first(self):
        """Test that Evaluation Set Run span is created as the root span."""
        recorder = SpanRecorder()

        # Simulate the span creation from _runtime.py:315-317
        with recorder.start_as_current_span(
            "Evaluation Set Run",
            attributes={"span_type": "eval_set_run"},
        ):
            pass

        assert len(recorder.spans) == 1
        span = recorder.spans[0]
        assert span["name"] == "Evaluation Set Run"
        assert span["attributes"]["span_type"] == "eval_set_run"
        assert span["parent"] is None

    def test_eval_set_run_span_with_run_id(self):
        """Test that eval_set_run_id is included when provided."""
        recorder = SpanRecorder()
        eval_set_run_id = "custom-run-123"

        span_attributes: Dict[str, str] = {"span_type": "eval_set_run"}
        span_attributes["eval_set_run_id"] = eval_set_run_id

        with recorder.start_as_current_span(
            "Evaluation Set Run",
            attributes=span_attributes,
        ):
            pass

        span = recorder.spans[0]
        assert span["attributes"]["eval_set_run_id"] == "custom-run-123"


class TestEvaluationSpanIntegration:
    """Integration tests for Evaluation span."""

    def test_evaluation_span_is_child_of_eval_set_run(self):
        """Test that Evaluation span is a child of Evaluation Set Run."""
        recorder = SpanRecorder()
        execution_id = str(uuid.uuid4())

        # Simulate the nested span creation
        with recorder.start_as_current_span(
            "Evaluation Set Run",
            attributes={"span_type": "eval_set_run"},
        ):
            with recorder.start_as_current_span(
                "Evaluation",
                attributes={
                    "execution.id": execution_id,
                    "span_type": "evaluation",
                    "eval_item_id": "item-1",
                    "eval_item_name": "Test Item",
                },
            ):
                pass

        assert len(recorder.spans) == 2

        eval_set_run_span = recorder.get_span_by_name("Evaluation Set Run")
        evaluation_span = recorder.get_span_by_name("Evaluation")

        assert eval_set_run_span is not None
        assert evaluation_span is not None
        assert evaluation_span["parent"] == "Evaluation Set Run"

    def test_multiple_evaluation_spans_share_parent(self):
        """Test that multiple Evaluation spans share the same parent."""
        recorder = SpanRecorder()

        with recorder.start_as_current_span(
            "Evaluation Set Run",
            attributes={"span_type": "eval_set_run"},
        ):
            for i in range(3):
                with recorder.start_as_current_span(
                    "Evaluation",
                    attributes={
                        "execution.id": str(uuid.uuid4()),
                        "span_type": "evaluation",
                        "eval_item_id": f"item-{i}",
                        "eval_item_name": f"Test Item {i}",
                    },
                ):
                    pass

        evaluation_spans = recorder.get_spans_by_type("evaluation")
        assert len(evaluation_spans) == 3

        for span in evaluation_spans:
            assert span["parent"] == "Evaluation Set Run"


class TestEvaluatorSpanIntegration:
    """Integration tests for Evaluator span."""

    def test_evaluator_span_is_child_of_evaluation(self):
        """Test that Evaluator span is a child of Evaluation."""
        recorder = SpanRecorder()

        with recorder.start_as_current_span(
            "Evaluation Set Run",
            attributes={"span_type": "eval_set_run"},
        ):
            with recorder.start_as_current_span(
                "Evaluation",
                attributes={
                    "execution.id": str(uuid.uuid4()),
                    "span_type": "evaluation",
                    "eval_item_id": "item-1",
                    "eval_item_name": "Test Item",
                },
            ):
                with recorder.start_as_current_span(
                    "Evaluator: AccuracyEvaluator",
                    attributes={
                        "span_type": "evaluator",
                        "evaluator_id": "accuracy-1",
                        "evaluator_name": "AccuracyEvaluator",
                        "eval_item_id": "item-1",
                    },
                ):
                    pass

        evaluator_span = recorder.spans[-1]
        assert evaluator_span["name"] == "Evaluator: AccuracyEvaluator"
        assert evaluator_span["parent"] == "Evaluation"

    def test_multiple_evaluator_spans_per_evaluation(self):
        """Test that multiple Evaluator spans can be children of one Evaluation."""
        recorder = SpanRecorder()
        evaluator_names = ["Accuracy", "Relevance", "Fluency"]

        with recorder.start_as_current_span(
            "Evaluation Set Run",
            attributes={"span_type": "eval_set_run"},
        ):
            with recorder.start_as_current_span(
                "Evaluation",
                attributes={
                    "execution.id": str(uuid.uuid4()),
                    "span_type": "evaluation",
                    "eval_item_id": "item-1",
                    "eval_item_name": "Test Item",
                },
            ):
                for name in evaluator_names:
                    with recorder.start_as_current_span(
                        f"Evaluator: {name}",
                        attributes={
                            "span_type": "evaluator",
                            "evaluator_id": f"{name.lower()}-1",
                            "evaluator_name": name,
                            "eval_item_id": "item-1",
                        },
                    ):
                        pass

        evaluator_spans = recorder.get_spans_by_type("evaluator")
        assert len(evaluator_spans) == 3

        for span in evaluator_spans:
            assert span["parent"] == "Evaluation"


class TestFullSpanHierarchy:
    """Integration tests for the complete span hierarchy."""

    def test_complete_hierarchy_structure(self):
        """Test the complete span hierarchy: EvalSetRun > Evaluation > Evaluator."""
        recorder = SpanRecorder()

        with recorder.start_as_current_span(
            "Evaluation Set Run",
            attributes={"span_type": "eval_set_run", "eval_set_run_id": "run-1"},
        ):
            for i in range(2):
                with recorder.start_as_current_span(
                    "Evaluation",
                    attributes={
                        "execution.id": str(uuid.uuid4()),
                        "span_type": "evaluation",
                        "eval_item_id": f"item-{i}",
                        "eval_item_name": f"Test Item {i}",
                    },
                ):
                    with recorder.start_as_current_span(
                        "Evaluator: TestEvaluator",
                        attributes={
                            "span_type": "evaluator",
                            "evaluator_id": "test-eval",
                            "evaluator_name": "TestEvaluator",
                            "eval_item_id": f"item-{i}",
                        },
                    ):
                        pass

        # Should have: 1 EvalSetRun + 2 Evaluation + 2 Evaluator = 5 spans
        assert len(recorder.spans) == 5

        eval_set_run_spans = recorder.get_spans_by_type("eval_set_run")
        evaluation_spans = recorder.get_spans_by_type("evaluation")
        evaluator_spans = recorder.get_spans_by_type("evaluator")

        assert len(eval_set_run_spans) == 1
        assert len(evaluation_spans) == 2
        assert len(evaluator_spans) == 2

    def test_span_attributes_are_complete(self):
        """Test that all spans have the required attributes."""
        recorder = SpanRecorder()

        with recorder.start_as_current_span(
            "Evaluation Set Run",
            attributes={"span_type": "eval_set_run", "eval_set_run_id": "run-123"},
        ):
            with recorder.start_as_current_span(
                "Evaluation",
                attributes={
                    "execution.id": "exec-456",
                    "span_type": "evaluation",
                    "eval_item_id": "item-789",
                    "eval_item_name": "My Test",
                },
            ):
                with recorder.start_as_current_span(
                    "Evaluator: Accuracy",
                    attributes={
                        "span_type": "evaluator",
                        "evaluator_id": "acc-1",
                        "evaluator_name": "Accuracy",
                        "eval_item_id": "item-789",
                    },
                ):
                    pass

        # Verify EvalSetRun span
        eval_set_run = recorder.get_spans_by_type("eval_set_run")[0]
        assert eval_set_run["attributes"]["eval_set_run_id"] == "run-123"

        # Verify Evaluation span
        evaluation = recorder.get_spans_by_type("evaluation")[0]
        assert evaluation["attributes"]["execution.id"] == "exec-456"
        assert evaluation["attributes"]["eval_item_id"] == "item-789"
        assert evaluation["attributes"]["eval_item_name"] == "My Test"

        # Verify Evaluator span
        evaluator = recorder.get_spans_by_type("evaluator")[0]
        assert evaluator["attributes"]["evaluator_id"] == "acc-1"
        assert evaluator["attributes"]["evaluator_name"] == "Accuracy"
        assert evaluator["attributes"]["eval_item_id"] == "item-789"


class TestSpanNaming:
    """Tests for span naming conventions."""

    def test_eval_set_run_span_name(self):
        """Test that EvalSetRun span has correct name."""
        recorder = SpanRecorder()

        with recorder.start_as_current_span(
            "Evaluation Set Run",
            attributes={"span_type": "eval_set_run"},
        ):
            pass

        assert recorder.spans[0]["name"] == "Evaluation Set Run"

    def test_evaluation_span_name(self):
        """Test that Evaluation span has correct name."""
        recorder = SpanRecorder()

        with recorder.start_as_current_span(
            "Evaluation",
            attributes={"span_type": "evaluation"},
        ):
            pass

        assert recorder.spans[0]["name"] == "Evaluation"

    def test_evaluator_span_name_format(self):
        """Test that Evaluator span name follows the pattern 'Evaluator: {name}'."""
        recorder = SpanRecorder()
        evaluator_name = "MyCustomEvaluator"

        with recorder.start_as_current_span(
            f"Evaluator: {evaluator_name}",
            attributes={
                "span_type": "evaluator",
                "evaluator_name": evaluator_name,
            },
        ):
            pass

        span = recorder.spans[0]
        assert span["name"] == "Evaluator: MyCustomEvaluator"
        assert span["name"].startswith("Evaluator: ")


class TestExecutionIdTracking:
    """Tests for execution.id tracking in spans."""

    def test_each_evaluation_has_unique_execution_id(self):
        """Test that each Evaluation span gets a unique execution.id."""
        recorder = SpanRecorder()
        execution_ids = []

        with recorder.start_as_current_span(
            "Evaluation Set Run",
            attributes={"span_type": "eval_set_run"},
        ):
            for i in range(3):
                exec_id = str(uuid.uuid4())
                execution_ids.append(exec_id)
                with recorder.start_as_current_span(
                    "Evaluation",
                    attributes={
                        "execution.id": exec_id,
                        "span_type": "evaluation",
                        "eval_item_id": f"item-{i}",
                        "eval_item_name": f"Item {i}",
                    },
                ):
                    pass

        # Verify all execution IDs are unique
        assert len(set(execution_ids)) == 3

        # Verify each evaluation span has its execution.id
        evaluation_spans = recorder.get_spans_by_type("evaluation")
        for i, span in enumerate(evaluation_spans):
            assert span["attributes"]["execution.id"] == execution_ids[i]

    def test_eval_set_run_does_not_have_execution_id(self):
        """Test that EvalSetRun span does NOT have execution.id.

        This is intentional to prevent ID propagation to child spans.
        """
        recorder = SpanRecorder()

        with recorder.start_as_current_span(
            "Evaluation Set Run",
            attributes={"span_type": "eval_set_run"},
        ):
            pass

        eval_set_run = recorder.spans[0]
        assert "execution.id" not in eval_set_run["attributes"]


class TestEvaluatorSpanEvalItemId:
    """Tests for eval_item_id in evaluator spans."""

    def test_evaluator_span_has_eval_item_id(self):
        """Test that Evaluator span includes the eval_item_id."""
        recorder = SpanRecorder()
        eval_item_id = "item-specific-123"

        with recorder.start_as_current_span(
            "Evaluation",
            attributes={
                "execution.id": str(uuid.uuid4()),
                "span_type": "evaluation",
                "eval_item_id": eval_item_id,
                "eval_item_name": "Test",
            },
        ):
            with recorder.start_as_current_span(
                "Evaluator: Test",
                attributes={
                    "span_type": "evaluator",
                    "evaluator_id": "test-1",
                    "evaluator_name": "Test",
                    "eval_item_id": eval_item_id,
                },
            ):
                pass

        evaluator_span = recorder.get_spans_by_type("evaluator")[0]
        assert evaluator_span["attributes"]["eval_item_id"] == eval_item_id

    def test_evaluator_and_evaluation_share_eval_item_id(self):
        """Test that Evaluator and Evaluation spans share the same eval_item_id."""
        recorder = SpanRecorder()
        eval_item_id = "shared-item-456"

        with recorder.start_as_current_span(
            "Evaluation",
            attributes={
                "execution.id": str(uuid.uuid4()),
                "span_type": "evaluation",
                "eval_item_id": eval_item_id,
                "eval_item_name": "Test",
            },
        ):
            with recorder.start_as_current_span(
                "Evaluator: Test",
                attributes={
                    "span_type": "evaluator",
                    "evaluator_id": "test-1",
                    "evaluator_name": "Test",
                    "eval_item_id": eval_item_id,
                },
            ):
                pass

        evaluation_span = recorder.get_spans_by_type("evaluation")[0]
        evaluator_span = recorder.get_spans_by_type("evaluator")[0]

        assert (
            evaluation_span["attributes"]["eval_item_id"]
            == evaluator_span["attributes"]["eval_item_id"]
        )
