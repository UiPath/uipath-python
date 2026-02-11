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
        mock_result1.evaluator_name = "eval1"
        mock_result1.result.score = 0.8

        mock_result2 = MagicMock()
        mock_result2.evaluator_name = "eval2"
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

    def test_set_evaluation_output_span_output_without_justification(self):
        """Test setting evaluation output span attributes without justification."""
        span = MockSpan()

        set_evaluation_output_span_output(
            span=span,  # type: ignore[arg-type]
            score=85.0,
            evaluator_id="evaluator-abc",
        )

        # Check output
        assert "output" in span.attributes
        output_data = json.loads(span.attributes["output"])

        assert output_data["type"] == 1
        assert output_data["score"] == 85.0
        assert output_data["evaluatorId"] == "evaluator-abc"
        assert "justification" not in output_data

    def test_set_evaluation_output_and_metadata_with_error(self):
        """Test setting evaluation span attributes with error."""
        span = MockSpan()

        set_evaluation_output_and_metadata(
            span=span,  # type: ignore[arg-type]
            evaluator_scores={"eval1": 0.0},
            execution_id="eval-error",
            has_error=True,
            error_message="Runtime error occurred",
        )

        # Check status is ERROR
        assert span._status is not None
        assert span._status.status_code == StatusCode.ERROR
        assert span._status.description is not None
        assert "Runtime error occurred" in span._status.description

    def test_set_evaluation_output_and_metadata_with_input_data(self):
        """Test setting evaluation span attributes with input data."""
        span = MockSpan()

        input_data = {"query": "test", "context": "example"}

        set_evaluation_output_and_metadata(
            span=span,  # type: ignore[arg-type]
            evaluator_scores={"eval1": 92.0},
            execution_id="eval-input-test",
            input_data=input_data,
            has_error=False,
        )

        # Verify input is set
        assert "input" in span.attributes
        input_parsed = json.loads(span.attributes["input"])
        assert input_parsed == {"query": "test", "context": "example"}

        # Verify output is set with scores
        output_data = json.loads(span.attributes["output"])
        assert output_data["scores"] == {"eval1": 92.0}

        # Verify other attributes
        assert span.attributes["agentId"] == "eval-input-test"


class TestHighLevelConfigurationFunctions:
    """Test the high-level span configuration functions."""

    @pytest.mark.asyncio
    async def test_configure_eval_set_run_span(self):
        """Test configuring evaluation set run span with scores dictionary."""
        span = MockSpan()

        evaluator_averages = {
            "TrajectoryEvaluator": 80.0,
            "JsonSimilarityEvaluator": 90.0,
        }

        # Mock schema
        mock_schema = MagicMock()
        mock_schema.input = {
            "type": "object",
            "properties": {"x": {"type": "number"}},
        }
        mock_schema.output = {"type": "string"}

        await configure_eval_set_run_span(
            span=span,  # type: ignore[arg-type]
            evaluator_averages=evaluator_averages,
            execution_id="exec-complete",
            schema=mock_schema,
            success=True,
        )

        # Verify scores dictionary
        output_data = json.loads(span.attributes["output"])
        assert "scores" in output_data
        assert output_data["scores"]["TrajectoryEvaluator"] == 80.0
        assert output_data["scores"]["JsonSimilarityEvaluator"] == 90.0

        # Verify metadata
        assert span.attributes["agentId"] == "exec-complete"
        assert span.attributes["agentName"] == "N/A"

        # Verify input schema
        input_schema_data = json.loads(span.attributes["inputSchema"])
        assert "properties" in input_schema_data
        assert input_schema_data["properties"]["x"]["type"] == "number"

        # Verify output schema
        output_schema_data = json.loads(span.attributes["outputSchema"])
        assert output_schema_data == {"type": "string"}

        # Verify status
        assert span._status is not None
        assert span._status.status_code == StatusCode.OK

    @pytest.mark.asyncio
    async def test_configure_eval_set_run_span_schema_error(self):
        """Test configuring evaluation set run span when schema fails."""
        span = MockSpan()

        evaluator_averages = {"ContainsEvaluator": 75.0}

        # Mock schema with missing fields
        mock_schema = MagicMock()
        mock_schema.input = None
        mock_schema.output = None

        await configure_eval_set_run_span(
            span=span,  # type: ignore[arg-type]
            evaluator_averages=evaluator_averages,
            execution_id="exec-error",
            schema=mock_schema,
            success=True,
        )

        # Verify scores still set
        output_data = json.loads(span.attributes["output"])
        assert output_data["scores"]["ContainsEvaluator"] == 75.0

        # Verify metadata still set
        assert span.attributes["agentId"] == "exec-error"

        # Verify schemas are empty objects when schema extraction fails
        assert span.attributes["inputSchema"] == "{}"
        assert span.attributes["outputSchema"] == "{}"

    @pytest.mark.asyncio
    async def test_configure_eval_set_run_span_normalizes_scores(self):
        """Test that scores are normalized to 0-100 range."""
        span = MockSpan()

        # Provide scores in 0-1 range
        evaluator_averages = {
            "eval1": 0.75,
            "eval2": 0.92,
        }

        mock_schema = MagicMock()
        mock_schema.input = {}
        mock_schema.output = {}

        await configure_eval_set_run_span(
            span=span,  # type: ignore[arg-type]
            evaluator_averages=evaluator_averages,
            execution_id="exec-normalize",
            schema=mock_schema,
            success=True,
        )

        # Verify scores are normalized to 0-100
        output_data = json.loads(span.attributes["output"])
        assert output_data["scores"]["eval1"] == 75.0
        assert output_data["scores"]["eval2"] == 92.0

    @pytest.mark.asyncio
    async def test_configure_evaluation_span(self):
        """Test configuring evaluation span with scores dictionary."""
        span = MockSpan()

        # Mock evaluation run results
        mock_result1 = MagicMock()
        mock_result1.evaluator_name = "TrajectoryEvaluator"
        mock_result1.result.score = 85.0

        mock_result2 = MagicMock()
        mock_result2.evaluator_name = "JsonSimilarityEvaluator"
        mock_result2.result.score = 92.5

        mock_evaluation_run_results = MagicMock()
        mock_evaluation_run_results.evaluation_run_results = [
            mock_result1,
            mock_result2,
        ]

        input_data = {"a": 1, "b": 2, "operator": "+"}

        await configure_evaluation_span(
            span=span,  # type: ignore[arg-type]
            evaluation_run_results=mock_evaluation_run_results,
            execution_id="eval-123",
            input_data=input_data,
            agent_execution_output=None,
        )

        # Verify scores dictionary
        output_data = json.loads(span.attributes["output"])
        assert "scores" in output_data
        assert output_data["scores"]["TrajectoryEvaluator"] == 85.0
        assert output_data["scores"]["JsonSimilarityEvaluator"] == 92.5

        # Verify input data
        input_attr = json.loads(span.attributes["input"])
        assert input_attr == {"a": 1, "b": 2, "operator": "+"}

        # Verify metadata
        assert span.attributes["agentId"] == "eval-123"
        assert span.attributes["agentName"] == "N/A"

        # Verify status (no error)
        assert span._status is not None
        assert span._status.status_code == StatusCode.OK

    @pytest.mark.asyncio
    async def test_configure_evaluation_span_with_error(self):
        """Test configuring evaluation span when agent execution has error."""
        span = MockSpan()

        # Mock evaluation run results (empty since agent failed)
        mock_evaluation_run_results = MagicMock()
        mock_evaluation_run_results.evaluation_run_results = []

        # Mock agent execution output with error
        mock_agent_output = MagicMock()
        mock_agent_output.result.error = "Agent execution failed"

        await configure_evaluation_span(
            span=span,  # type: ignore[arg-type]
            evaluation_run_results=mock_evaluation_run_results,
            execution_id="eval-error",
            input_data=None,
            agent_execution_output=mock_agent_output,
        )

        # Verify empty scores dictionary
        output_data = json.loads(span.attributes["output"])
        assert output_data["scores"] == {}

        # Verify error status
        assert span._status is not None
        assert span._status.status_code == StatusCode.ERROR
        assert span._status.description is not None
        assert "Agent execution failed" in span._status.description

    @pytest.mark.asyncio
    async def test_configure_evaluation_span_without_agent_output(self):
        """Test configuring evaluation span without agent execution output."""
        span = MockSpan()

        mock_result = MagicMock()
        mock_result.evaluator_name = "TrajectoryEvaluator"
        mock_result.result.score = 85.0

        mock_evaluation_run_results = MagicMock()
        mock_evaluation_run_results.evaluation_run_results = [mock_result]

        await configure_evaluation_span(
            span=span,  # type: ignore[arg-type]
            evaluation_run_results=mock_evaluation_run_results,
            execution_id="eval-no-output",
            agent_execution_output=None,
        )

        # Verify it doesn't crash and sets OK status
        assert span._status is not None
        assert span._status.status_code == StatusCode.OK

        # Verify scores are set
        output_data = json.loads(span.attributes["output"])
        assert output_data["scores"]["TrajectoryEvaluator"] == 85.0
