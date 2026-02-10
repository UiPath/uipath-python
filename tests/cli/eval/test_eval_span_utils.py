"""Unit tests for evaluation span utility functions."""

import json
from typing import Any, Dict, Optional
from unittest.mock import MagicMock

import pytest
from opentelemetry.trace import Status, StatusCode

from uipath._cli._evals._span_utils import (
    EvalSetRunOutput,
    EvaluationOutput,
    EvaluationOutputSpanOutput,
    configure_eval_set_run_span,
    configure_evaluation_span,
    extract_evaluator_scores,
    normalize_score_to_100,
    set_eval_set_run_output_and_metadata,
    set_evaluation_output_and_metadata,
    set_evaluation_output_span_output,
)


class MockSpan:
    """Mock span for testing."""

    def __init__(self) -> None:
        self.attributes: Dict[str, Any] = {}
        self._status: Optional[Status] = None

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def set_status(self, status: Status) -> None:
        self._status = status


class TestPydanticModels:
    """Test the Pydantic models for span outputs."""

    def test_eval_set_run_output_model(self):
        """Test EvalSetRunOutput model serialization."""
        output = EvalSetRunOutput(scores={"eval1": 85.5, "eval2": 92.3})
        json_str = output.model_dump_json(by_alias=True)
        data = json.loads(json_str)

        assert data == {"scores": {"eval1": 85.5, "eval2": 92.3}}
        assert isinstance(data["scores"], dict)
        assert isinstance(data["scores"]["eval1"], float)

    def test_evaluation_output_model(self):
        """Test EvaluationOutput model serialization."""
        output = EvaluationOutput(scores={"eval1": 90.5, "eval2": 88.0})
        json_str = output.model_dump_json(by_alias=True)
        data = json.loads(json_str)

        assert data == {"scores": {"eval1": 90.5, "eval2": 88.0}}
        assert isinstance(data["scores"], dict)

    def test_evaluation_output_span_output_model_with_justification(self):
        """Test EvaluationOutputSpanOutput model with justification."""
        output = EvaluationOutputSpanOutput(
            score=75.5,
            evaluator_id="eval-123",
            justification="The output is semantically similar",
        )
        json_str = output.model_dump_json(by_alias=True, exclude_none=True)
        data = json.loads(json_str)

        assert data["type"] == 1
        assert data["score"] == 75.5
        assert data["evaluatorId"] == "eval-123"
        assert data["justification"] == "The output is semantically similar"

    def test_evaluation_output_span_output_model_without_justification(self):
        """Test EvaluationOutputSpanOutput model without justification."""
        output = EvaluationOutputSpanOutput(score=75.5, evaluator_id="eval-456")
        json_str = output.model_dump_json(by_alias=True, exclude_none=True)
        data = json.loads(json_str)

        assert data["type"] == 1
        assert data["score"] == 75.5
        assert data["evaluatorId"] == "eval-456"
        assert "justification" not in data


class TestNormalizationFunctions:
    """Test the score normalization functions."""

    def test_normalize_score_0_to_1_range(self):
        """Test normalizing scores in 0-1 range to 0-100."""
        assert normalize_score_to_100(0.0) == 0.0
        assert normalize_score_to_100(0.5) == 50.0
        assert normalize_score_to_100(1.0) == 100.0
        assert normalize_score_to_100(0.857142) == 85.71

    def test_normalize_score_0_to_100_range(self):
        """Test that scores in 0-100 range stay the same."""
        assert normalize_score_to_100(0.0) == 0.0
        assert normalize_score_to_100(50.0) == 50.0
        assert normalize_score_to_100(100.0) == 100.0
        assert normalize_score_to_100(85.71) == 85.71

    def test_normalize_score_clamps_out_of_range(self):
        """Test that out-of-range scores are clamped."""
        assert normalize_score_to_100(-10.0) == 0.0
        assert normalize_score_to_100(150.0) == 100.0

    def test_extract_evaluator_scores(self):
        """Test extracting evaluator scores from results."""
        mock_result1 = MagicMock()
        mock_result1.evaluator_id = "eval1"
        mock_result1.result.score = 0.8

        mock_result2 = MagicMock()
        mock_result2.evaluator_id = "eval2"
        mock_result2.result.score = 90.0

        mock_evaluation_run_results = MagicMock()
        mock_evaluation_run_results.evaluation_run_results = [
            mock_result1,
            mock_result2,
        ]

        scores = extract_evaluator_scores(mock_evaluation_run_results)

        assert scores == {"eval1": 80.0, "eval2": 90.0}

    def test_extract_evaluator_scores_empty(self):
        """Test extracting scores from empty results."""
        mock_evaluation_run_results = MagicMock()
        mock_evaluation_run_results.evaluation_run_results = []

        scores = extract_evaluator_scores(mock_evaluation_run_results)

        assert scores == {}


class TestSetSpanAttributeFunctions:
    """Test the low-level span attribute setting functions."""

    def test_set_eval_set_run_output_and_metadata(self):
        """Test setting evaluation set run span attributes."""
        span = MockSpan()

        set_eval_set_run_output_and_metadata(
            span=span,  # type: ignore[arg-type]
            evaluator_scores={"eval1": 82.5, "eval2": 90.0},
            execution_id="exec-123",
            input_schema={"type": "object"},
            output_schema={"type": "string"},
            success=True,
        )

        # Check output
        assert "output" in span.attributes
        output_data = json.loads(span.attributes["output"])
        assert output_data == {"scores": {"eval1": 82.5, "eval2": 90.0}}

        # Check metadata
        assert span.attributes["agentId"] == "exec-123"
        assert span.attributes["agentName"] == "N/A"

        # Check schemas
        input_schema_data = json.loads(span.attributes["inputSchema"])
        assert input_schema_data == {"type": "object"}

        output_schema_data = json.loads(span.attributes["outputSchema"])
        assert output_schema_data == {"type": "string"}

        # Check status
        assert span._status is not None
        assert span._status.status_code == StatusCode.OK

    def test_set_evaluation_output_and_metadata(self):
        """Test setting evaluation span attributes."""
        span = MockSpan()

        set_evaluation_output_and_metadata(
            span=span,  # type: ignore[arg-type]
            evaluator_scores={"eval1": 88.3, "eval2": 92.0},
            execution_id="eval-789",
            has_error=False,
            error_message=None,
        )

        # Check output
        assert "output" in span.attributes
        output_data = json.loads(span.attributes["output"])
        assert output_data == {"scores": {"eval1": 88.3, "eval2": 92.0}}

        # Check metadata
        assert span.attributes["agentId"] == "eval-789"
        assert span.attributes["agentName"] == "N/A"

        # Check status is OK
        assert span._status is not None
        assert span._status.status_code == StatusCode.OK

    def test_set_evaluation_output_span_output_with_justification(self):
        """Test setting evaluation output span attributes with justification."""
        span = MockSpan()

        set_evaluation_output_span_output(
            span=span,  # type: ignore[arg-type]
            score=92.7,
            evaluator_id="evaluator-xyz",
            justification="The answer is correct and well-formatted",
        )

        # Check output
        assert "output" in span.attributes
        output_data = json.loads(span.attributes["output"])

        assert output_data["type"] == 1
        assert output_data["score"] == 92.7
        assert output_data["evaluatorId"] == "evaluator-xyz"
        assert (
            output_data["justification"] == "The answer is correct and well-formatted"
        )

    def test_set_evaluation_output_span_output_normalizes_0_to_1_score(self):
        """Test that 0-1 scores are normalized to 0-100."""
        span = MockSpan()

        set_evaluation_output_span_output(
            span=span,  # type: ignore[arg-type]
            score=0.857,
            evaluator_id="evaluator-abc",
        )

        # Check output
        assert "output" in span.attributes
        output_data = json.loads(span.attributes["output"])

        assert output_data["score"] == 85.7  # 0.857 * 100
