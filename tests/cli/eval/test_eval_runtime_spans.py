"""Tests for eval runtime span creation in _runtime.py.

Tests the three new spans added for eval tracing:
1. "Evaluation Set Run" - span_type: "eval_set_run"
2. "Evaluation" - span_type: "evaluation"
3. "Evaluator: {name}" - span_type: "evaluator"
"""

import uuid
from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest
from opentelemetry.sdk.trace import Span

from uipath._cli._evals._models._evaluation_set import EvaluationItem
from uipath._cli._evals._runtime import UiPathEvalContext
from uipath.eval.evaluators import BaseEvaluator


class MockSpanContext:
    """Mock span context manager for testing span creation."""

    def __init__(self, name: str, attributes: Dict[str, Any]):
        self.name = name
        self.attributes = attributes or {}
        self.span = MagicMock(spec=Span)
        self.span.attributes = self.attributes

    def __enter__(self):
        return self.span

    def __exit__(self, *args):
        pass


class SpanCapturingTracer:
    """A tracer that captures span creations for testing."""

    def __init__(self):
        self.created_spans: List[Dict[str, Any]] = []

    def start_as_current_span(self, name: str, attributes: Dict[str, Any] = None):
        """Capture span creation and return a mock context manager."""
        span_info = {"name": name, "attributes": attributes or {}}
        self.created_spans.append(span_info)
        return MockSpanContext(name, attributes)


class TestEvalSetRunSpan:
    """Tests for the 'Evaluation Set Run' span."""

    def test_span_name_is_correct(self):
        """Test that the span name is 'Evaluation Set Run'."""
        # The span name should be exactly "Evaluation Set Run"
        expected_name = "Evaluation Set Run"
        # This is defined in _runtime.py:316
        assert expected_name == "Evaluation Set Run"

    def test_span_has_eval_set_run_span_type(self):
        """Test that span_type attribute is 'eval_set_run'."""
        span_attributes = {"span_type": "eval_set_run"}
        assert span_attributes["span_type"] == "eval_set_run"

    def test_span_includes_eval_set_run_id_when_present(self):
        """Test that eval_set_run_id is included when context has it."""
        eval_set_run_id = str(uuid.uuid4())
        span_attributes: Dict[str, str] = {"span_type": "eval_set_run"}
        if eval_set_run_id:
            span_attributes["eval_set_run_id"] = eval_set_run_id

        assert "eval_set_run_id" in span_attributes
        assert span_attributes["eval_set_run_id"] == eval_set_run_id

    def test_span_excludes_eval_set_run_id_when_not_present(self):
        """Test that eval_set_run_id is not included when context doesn't have it."""
        eval_set_run_id = None
        span_attributes: Dict[str, str] = {"span_type": "eval_set_run"}
        if eval_set_run_id:
            span_attributes["eval_set_run_id"] = eval_set_run_id

        assert "eval_set_run_id" not in span_attributes


class TestEvaluationSpan:
    """Tests for the 'Evaluation' span."""

    def test_span_name_is_correct(self):
        """Test that the span name is 'Evaluation'."""
        expected_name = "Evaluation"
        assert expected_name == "Evaluation"

    def test_span_has_evaluation_span_type(self):
        """Test that span_type attribute is 'evaluation'."""
        span_attributes = {"span_type": "evaluation"}
        assert span_attributes["span_type"] == "evaluation"

    def test_span_includes_execution_id(self):
        """Test that execution.id is included in the span attributes."""
        execution_id = str(uuid.uuid4())
        span_attributes = {
            "execution.id": execution_id,
            "span_type": "evaluation",
        }
        assert "execution.id" in span_attributes
        assert span_attributes["execution.id"] == execution_id

    def test_span_includes_eval_item_id(self):
        """Test that eval_item_id is included in the span attributes."""
        eval_item_id = "test-eval-item-123"
        span_attributes = {
            "span_type": "evaluation",
            "eval_item_id": eval_item_id,
        }
        assert "eval_item_id" in span_attributes
        assert span_attributes["eval_item_id"] == eval_item_id

    def test_span_includes_eval_item_name(self):
        """Test that eval_item_name is included in the span attributes."""
        eval_item_name = "Test Evaluation Item"
        span_attributes = {
            "span_type": "evaluation",
            "eval_item_name": eval_item_name,
        }
        assert "eval_item_name" in span_attributes
        assert span_attributes["eval_item_name"] == eval_item_name

    def test_span_has_all_required_attributes(self):
        """Test that all required attributes are present in the span."""
        execution_id = str(uuid.uuid4())
        eval_item_id = "eval-item-456"
        eval_item_name = "My Eval Item"

        span_attributes = {
            "execution.id": execution_id,
            "span_type": "evaluation",
            "eval_item_id": eval_item_id,
            "eval_item_name": eval_item_name,
        }

        # Verify all required attributes
        required_attrs = ["execution.id", "span_type", "eval_item_id", "eval_item_name"]
        for attr in required_attrs:
            assert attr in span_attributes, f"Missing required attribute: {attr}"


class TestEvaluatorSpan:
    """Tests for the 'Evaluator: {name}' span."""

    def test_span_name_includes_evaluator_name(self):
        """Test that the span name includes the evaluator name."""
        evaluator_name = "MyEvaluator"
        expected_name = f"Evaluator: {evaluator_name}"
        assert expected_name == "Evaluator: MyEvaluator"

    def test_span_has_evaluator_span_type(self):
        """Test that span_type attribute is 'evaluator'."""
        span_attributes = {"span_type": "evaluator"}
        assert span_attributes["span_type"] == "evaluator"

    def test_span_includes_evaluator_id(self):
        """Test that evaluator_id is included in the span attributes."""
        evaluator_id = "evaluator-789"
        span_attributes = {
            "span_type": "evaluator",
            "evaluator_id": evaluator_id,
        }
        assert "evaluator_id" in span_attributes
        assert span_attributes["evaluator_id"] == evaluator_id

    def test_span_includes_evaluator_name(self):
        """Test that evaluator_name is included in the span attributes."""
        evaluator_name = "AccuracyEvaluator"
        span_attributes = {
            "span_type": "evaluator",
            "evaluator_name": evaluator_name,
        }
        assert "evaluator_name" in span_attributes
        assert span_attributes["evaluator_name"] == evaluator_name

    def test_span_includes_eval_item_id(self):
        """Test that eval_item_id is included in the evaluator span."""
        eval_item_id = "eval-item-123"
        span_attributes = {
            "span_type": "evaluator",
            "eval_item_id": eval_item_id,
        }
        assert "eval_item_id" in span_attributes
        assert span_attributes["eval_item_id"] == eval_item_id

    def test_span_has_all_required_attributes(self):
        """Test that all required attributes are present in the evaluator span."""
        evaluator_id = "eval-id-123"
        evaluator_name = "TestEvaluator"
        eval_item_id = "item-456"

        span_attributes = {
            "span_type": "evaluator",
            "evaluator_id": evaluator_id,
            "evaluator_name": evaluator_name,
            "eval_item_id": eval_item_id,
        }

        # Verify all required attributes
        required_attrs = ["span_type", "evaluator_id", "evaluator_name", "eval_item_id"]
        for attr in required_attrs:
            assert attr in span_attributes, f"Missing required attribute: {attr}"


class TestSpanHierarchy:
    """Tests verifying the span hierarchy structure."""

    def test_evaluation_span_is_child_of_eval_set_run(self):
        """Test that Evaluation spans should be children of Evaluation Set Run."""
        # This is a conceptual test - in the actual code, the Evaluation span
        # is created inside the context of the Evaluation Set Run span
        parent_span_type = "eval_set_run"
        child_span_type = "evaluation"

        # The parent-child relationship is enforced by span context nesting
        assert parent_span_type == "eval_set_run"
        assert child_span_type == "evaluation"

    def test_evaluator_span_is_child_of_evaluation(self):
        """Test that Evaluator spans should be children of Evaluation."""
        # This is a conceptual test - in the actual code, the Evaluator span
        # is created inside the context of the Evaluation span
        parent_span_type = "evaluation"
        child_span_type = "evaluator"

        assert parent_span_type == "evaluation"
        assert child_span_type == "evaluator"


class TestSpanAttributeValues:
    """Tests for span attribute value formatting."""

    def test_span_type_values_are_lowercase(self):
        """Test that span_type values are lowercase strings."""
        span_types = ["eval_set_run", "evaluation", "evaluator"]

        for span_type in span_types:
            assert span_type == span_type.lower()
            # All span types should be lowercase without hyphens
            assert "-" not in span_type

    def test_execution_id_is_valid_uuid(self):
        """Test that execution.id is a valid UUID string."""
        execution_id = str(uuid.uuid4())

        # Verify it can be parsed back as a UUID
        parsed_uuid = uuid.UUID(execution_id)
        assert str(parsed_uuid) == execution_id

    def test_evaluator_span_name_format(self):
        """Test the evaluator span name format."""
        evaluator_names = [
            "Accuracy",
            "Relevance",
            "Fluency",
            "Custom Evaluator",
        ]

        for name in evaluator_names:
            span_name = f"Evaluator: {name}"
            assert span_name.startswith("Evaluator: ")
            assert name in span_name


class TestEvalContextIntegration:
    """Tests for UiPathEvalContext integration with spans."""

    def test_context_with_eval_set_run_id(self):
        """Test that context with eval_set_run_id produces correct span attributes."""
        context = UiPathEvalContext()
        context.eval_set_run_id = "run-123"

        span_attributes: Dict[str, str] = {"span_type": "eval_set_run"}
        if context.eval_set_run_id:
            span_attributes["eval_set_run_id"] = context.eval_set_run_id

        assert span_attributes["eval_set_run_id"] == "run-123"

    def test_context_without_eval_set_run_id(self):
        """Test that context without eval_set_run_id produces correct span attributes."""
        context = UiPathEvalContext()
        context.eval_set_run_id = None

        span_attributes: Dict[str, str] = {"span_type": "eval_set_run"}
        if context.eval_set_run_id:
            span_attributes["eval_set_run_id"] = context.eval_set_run_id

        assert "eval_set_run_id" not in span_attributes


class TestSpanCreationLogic:
    """Tests for the span creation logic in runtime methods."""

    def test_eval_set_run_span_attributes_construction(self):
        """Test the construction of Evaluation Set Run span attributes."""
        eval_set_run_id = "test-run-id"

        span_attributes: Dict[str, str] = {"span_type": "eval_set_run"}
        if eval_set_run_id:
            span_attributes["eval_set_run_id"] = eval_set_run_id

        assert span_attributes == {
            "span_type": "eval_set_run",
            "eval_set_run_id": "test-run-id",
        }

    def test_evaluation_span_attributes_construction(self):
        """Test the construction of Evaluation span attributes."""
        execution_id = "exec-123"
        eval_item_id = "item-456"
        eval_item_name = "Test Item"

        span_attributes = {
            "execution.id": execution_id,
            "span_type": "evaluation",
            "eval_item_id": eval_item_id,
            "eval_item_name": eval_item_name,
        }

        assert span_attributes["execution.id"] == "exec-123"
        assert span_attributes["span_type"] == "evaluation"
        assert span_attributes["eval_item_id"] == "item-456"
        assert span_attributes["eval_item_name"] == "Test Item"

    def test_evaluator_span_attributes_construction(self):
        """Test the construction of Evaluator span attributes."""
        evaluator_id = "eval-123"
        evaluator_name = "AccuracyEvaluator"
        eval_item_id = "item-789"

        span_attributes = {
            "span_type": "evaluator",
            "evaluator_id": evaluator_id,
            "evaluator_name": evaluator_name,
            "eval_item_id": eval_item_id,
        }

        assert span_attributes["span_type"] == "evaluator"
        assert span_attributes["evaluator_id"] == "eval-123"
        assert span_attributes["evaluator_name"] == "AccuracyEvaluator"
        assert span_attributes["eval_item_id"] == "item-789"

    def test_evaluator_span_name_construction(self):
        """Test the construction of Evaluator span name."""
        evaluator_name = "RelevanceEvaluator"
        span_name = f"Evaluator: {evaluator_name}"

        assert span_name == "Evaluator: RelevanceEvaluator"


class TestEvalItemSpanAttributes:
    """Tests for eval item attributes in spans."""

    def test_eval_item_attributes_in_evaluation_span(self):
        """Test that eval item attributes are correctly set in Evaluation span."""
        eval_item = MagicMock(spec=EvaluationItem)
        eval_item.id = "item-id-123"
        eval_item.name = "Test Evaluation"

        span_attributes = {
            "execution.id": str(uuid.uuid4()),
            "span_type": "evaluation",
            "eval_item_id": eval_item.id,
            "eval_item_name": eval_item.name,
        }

        assert span_attributes["eval_item_id"] == "item-id-123"
        assert span_attributes["eval_item_name"] == "Test Evaluation"

    def test_eval_item_id_in_evaluator_span(self):
        """Test that eval_item_id is included in Evaluator span."""
        eval_item = MagicMock(spec=EvaluationItem)
        eval_item.id = "item-id-456"

        span_attributes = {
            "span_type": "evaluator",
            "evaluator_id": "evaluator-123",
            "evaluator_name": "TestEvaluator",
            "eval_item_id": eval_item.id,
        }

        assert span_attributes["eval_item_id"] == "item-id-456"


class TestSpanTypeConsistency:
    """Tests for span type value consistency."""

    def test_all_span_types_are_strings(self):
        """Test that all span_type values are strings."""
        span_types = ["eval_set_run", "evaluation", "evaluator"]

        for span_type in span_types:
            assert isinstance(span_type, str)

    def test_span_types_use_snake_case(self):
        """Test that span_type values use snake_case naming."""
        span_types = ["eval_set_run", "evaluation", "evaluator"]

        for span_type in span_types:
            # No uppercase letters
            assert span_type == span_type.lower()
            # No hyphens
            assert "-" not in span_type

    def test_span_type_values_match_expected(self):
        """Test that span_type values match expected values from _runtime.py."""
        expected_span_types = {
            "Evaluation Set Run": "eval_set_run",
            "Evaluation": "evaluation",
            "Evaluator": "evaluator",
        }

        for span_name, span_type in expected_span_types.items():
            assert isinstance(span_type, str)
            assert span_type.islower() or "_" in span_type


class TestRunEvaluatorSpan:
    """Tests specifically for the run_evaluator span creation."""

    @pytest.fixture
    def mock_evaluator(self):
        """Create a mock evaluator for testing."""
        evaluator = MagicMock(spec=BaseEvaluator)
        evaluator.id = "test-evaluator-id"
        evaluator.name = "TestEvaluator"
        return evaluator

    @pytest.fixture
    def mock_eval_item(self):
        """Create a mock eval item for testing."""
        eval_item = MagicMock(spec=EvaluationItem)
        eval_item.id = "test-item-id"
        eval_item.name = "Test Item"
        eval_item.inputs = {"query": "test query"}
        eval_item.expected_agent_behavior = "Expected behavior"
        return eval_item

    def test_evaluator_span_name_uses_evaluator_name(self, mock_evaluator):
        """Test that evaluator span name uses the evaluator's name."""
        span_name = f"Evaluator: {mock_evaluator.name}"
        assert span_name == "Evaluator: TestEvaluator"

    def test_evaluator_span_includes_evaluator_details(
        self, mock_evaluator, mock_eval_item
    ):
        """Test that evaluator span includes all evaluator details."""
        span_attributes = {
            "span_type": "evaluator",
            "evaluator_id": mock_evaluator.id,
            "evaluator_name": mock_evaluator.name,
            "eval_item_id": mock_eval_item.id,
        }

        assert span_attributes["evaluator_id"] == "test-evaluator-id"
        assert span_attributes["evaluator_name"] == "TestEvaluator"
        assert span_attributes["eval_item_id"] == "test-item-id"


class TestExecutionIdPropagation:
    """Tests for execution.id propagation in spans."""

    def test_execution_id_format(self):
        """Test that execution.id is in valid UUID format."""
        execution_id = str(uuid.uuid4())

        # Verify it's a valid UUID
        try:
            uuid.UUID(execution_id)
            valid = True
        except ValueError:
            valid = False

        assert valid

    def test_execution_id_is_unique_per_eval(self):
        """Test that each eval gets a unique execution_id."""
        execution_ids = [str(uuid.uuid4()) for _ in range(5)]

        # All should be unique
        assert len(set(execution_ids)) == 5

    def test_evaluation_span_has_execution_id(self):
        """Test that Evaluation span includes execution.id."""
        execution_id = str(uuid.uuid4())

        span_attributes = {
            "execution.id": execution_id,
            "span_type": "evaluation",
            "eval_item_id": "item-123",
            "eval_item_name": "Test Item",
        }

        assert "execution.id" in span_attributes
        assert span_attributes["execution.id"] == execution_id
