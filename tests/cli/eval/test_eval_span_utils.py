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
    calculate_evaluation_average_score,
    calculate_overall_score,
    configure_eval_set_run_span,
    configure_evaluation_span,
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
        output = EvalSetRunOutput(score=85)
        json_str = output.model_dump_json(by_alias=True)
        data = json.loads(json_str)

        assert data == {"score": 85}
        assert isinstance(data["score"], int)

    def test_evaluation_output_model(self):
        """Test EvaluationOutput model serialization."""
        output = EvaluationOutput(score=90)
        json_str = output.model_dump_json(by_alias=True)
        data = json.loads(json_str)

        assert data == {"score": 90}
        assert isinstance(data["score"], int)

    def test_evaluation_output_span_output_model_with_justification(self):
        """Test EvaluationOutputSpanOutput model with justification."""
        output = EvaluationOutputSpanOutput(
            value=75.5,
            evaluator_id="eval-123",
            justification="The output is semantically similar",
        )
        json_str = output.model_dump_json(by_alias=True, exclude_none=True)
        data = json.loads(json_str)

        assert data["type"] == 1
        assert data["value"] == 75.5
        assert data["evaluatorId"] == "eval-123"
        assert data["justification"] == "The output is semantically similar"

    def test_evaluation_output_span_output_model_without_justification(self):
        """Test EvaluationOutputSpanOutput model without justification."""
        output = EvaluationOutputSpanOutput(value=75.5, evaluator_id="eval-456")
        json_str = output.model_dump_json(by_alias=True, exclude_none=True)
        data = json.loads(json_str)

        assert data["type"] == 1
        assert data["value"] == 75.5
        assert data["evaluatorId"] == "eval-456"
        assert "justification" not in data


class TestCalculationFunctions:
    """Test the score calculation functions."""

    def test_calculate_overall_score_with_evaluators(self):
        """Test calculate_overall_score with multiple evaluators."""
        evaluator_averages = {
            "eval1": 80.0,
            "eval2": 90.0,
            "eval3": 70.0,
        }
        result = calculate_overall_score(evaluator_averages)

        assert result == 80.0  # (80 + 90 + 70) / 3

    def test_calculate_overall_score_empty(self):
        """Test calculate_overall_score with no evaluators."""
        result = calculate_overall_score({})

        assert result == 0.0

    def test_calculate_evaluation_average_score_with_results(self):
        """Test calculate_evaluation_average_score with results."""
        mock_result1 = MagicMock()
        mock_result1.result.score = 80.0

        mock_result2 = MagicMock()
        mock_result2.result.score = 90.0

        mock_evaluation_run_results = MagicMock()
        mock_evaluation_run_results.evaluation_run_results = [
            mock_result1,
            mock_result2,
        ]

        result = calculate_evaluation_average_score(mock_evaluation_run_results)

        assert result == 85.0  # (80 + 90) / 2

    def test_calculate_evaluation_average_score_empty(self):
        """Test calculate_evaluation_average_score with no results."""
        mock_evaluation_run_results = MagicMock()
        mock_evaluation_run_results.evaluation_run_results = []

        result = calculate_evaluation_average_score(mock_evaluation_run_results)

        assert result == 0.0


class TestSetSpanAttributeFunctions:
    """Test the low-level span attribute setting functions."""

    def test_set_eval_set_run_output_and_metadata(self):
        """Test setting evaluation set run span attributes."""
        span = MockSpan()

        set_eval_set_run_output_and_metadata(
            span=span,  # type: ignore[arg-type]
            overall_score=82.5,
            execution_id="exec-123",
            input_schema={"type": "object"},
            output_schema={"type": "string"},
            success=True,
        )

        # Check output
        assert "output" in span.attributes
        output_data = json.loads(span.attributes["output"])
        assert output_data == {"score": 82}

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

    def test_set_eval_set_run_output_and_metadata_with_none_schemas(self):
        """Test setting span attributes with None schemas."""
        span = MockSpan()

        set_eval_set_run_output_and_metadata(
            span=span,  # type: ignore[arg-type]
            overall_score=75.0,
            execution_id="exec-456",
            input_schema=None,
            output_schema=None,
            success=True,
        )

        # Check schemas default to empty objects
        input_schema_data = json.loads(span.attributes["inputSchema"])
        assert input_schema_data == {}

        output_schema_data = json.loads(span.attributes["outputSchema"])
        assert output_schema_data == {}

    def test_set_evaluation_output_and_metadata(self):
        """Test setting evaluation span attributes."""
        span = MockSpan()

        set_evaluation_output_and_metadata(
            span=span,  # type: ignore[arg-type]
            avg_score=88.3,
            execution_id="eval-789",
            has_error=False,
            error_message=None,
        )

        # Check output
        assert "output" in span.attributes
        output_data = json.loads(span.attributes["output"])
        assert output_data == {"score": 88}

        # Check metadata
        assert span.attributes["agentId"] == "eval-789"
        assert span.attributes["agentName"] == "N/A"

        # Check status is OK
        assert span._status is not None
        assert span._status.status_code == StatusCode.OK

    def test_set_evaluation_output_and_metadata_with_error(self):
        """Test setting evaluation span attributes with error."""
        span = MockSpan()

        set_evaluation_output_and_metadata(
            span=span,  # type: ignore[arg-type]
            avg_score=0.0,
            execution_id="eval-error",
            has_error=True,
            error_message="Runtime error occurred",
        )

        # Check status is ERROR
        assert span._status is not None
        assert span._status.status_code == StatusCode.ERROR
        assert span._status.description is not None
        assert "Runtime error occurred" in span._status.description

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
        assert output_data["value"] == 92.7
        assert output_data["evaluatorId"] == "evaluator-xyz"
        assert (
            output_data["justification"] == "The answer is correct and well-formatted"
        )

    def test_set_evaluation_output_span_output_without_justification(self):
        """Test setting evaluation output span attributes without justification."""
        span = MockSpan()

        set_evaluation_output_span_output(
            span=span,  # type: ignore[arg-type]
            score=85.0,
            evaluator_id="evaluator-abc",
            justification=None,
        )

        # Check output
        assert "output" in span.attributes
        output_data = json.loads(span.attributes["output"])

        assert output_data["type"] == 1
        assert output_data["value"] == 85.0
        assert output_data["evaluatorId"] == "evaluator-abc"
        assert "justification" not in output_data


class TestHighLevelConfigurationFunctions:
    """Test the high-level span configuration functions."""

    @pytest.mark.asyncio
    async def test_configure_eval_set_run_span(self):
        """Test configuring evaluation set run span."""
        span = MockSpan()

        evaluator_averages = {
            "eval1": 80.0,
            "eval2": 90.0,
        }

        # Mock runtime and get_schema_func
        mock_runtime = MagicMock()
        mock_schema = MagicMock()
        mock_schema.input = {
            "type": "object",
            "properties": {"x": {"type": "number"}},
        }
        mock_schema.output = {"type": "string"}

        async def mock_get_schema(runtime):
            return mock_schema

        await configure_eval_set_run_span(
            span=span,  # type: ignore[arg-type]
            evaluator_averages=evaluator_averages,
            execution_id="exec-complete",
            runtime=mock_runtime,
            get_schema_func=mock_get_schema,
            success=True,
        )

        # Verify score calculation
        output_data = json.loads(span.attributes["output"])
        assert output_data["score"] == 85  # (80 + 90) / 2

        # Verify metadata
        assert span.attributes["agentId"] == "exec-complete"
        assert span.attributes["agentName"] == "N/A"

        # Verify schemas
        input_schema_data = json.loads(span.attributes["inputSchema"])
        assert "properties" in input_schema_data
        assert input_schema_data["properties"]["x"]["type"] == "number"

        # Verify status
        assert span._status is not None
        assert span._status.status_code == StatusCode.OK

    @pytest.mark.asyncio
    async def test_configure_eval_set_run_span_schema_error(self):
        """Test configuring evaluation set run span when schema fails."""
        span = MockSpan()

        evaluator_averages = {"eval1": 75.0}

        # Mock get_schema_func that raises exception
        async def mock_get_schema_error(runtime):
            raise Exception("Schema not found")

        await configure_eval_set_run_span(
            span=span,  # type: ignore[arg-type]
            evaluator_averages=evaluator_averages,
            execution_id="exec-no-schema",
            runtime=MagicMock(),
            get_schema_func=mock_get_schema_error,
            success=True,
        )

        # Verify schemas default to empty
        input_schema_data = json.loads(span.attributes["inputSchema"])
        assert input_schema_data == {}

        output_schema_data = json.loads(span.attributes["outputSchema"])
        assert output_schema_data == {}

    @pytest.mark.asyncio
    async def test_configure_evaluation_span(self):
        """Test configuring evaluation span."""
        span = MockSpan()

        # Mock evaluation results
        mock_result1 = MagicMock()
        mock_result1.result.score = 70.0

        mock_result2 = MagicMock()
        mock_result2.result.score = 90.0

        mock_evaluation_run_results = MagicMock()
        mock_evaluation_run_results.evaluation_run_results = [
            mock_result1,
            mock_result2,
        ]

        # Mock agent execution output (no error)
        mock_agent_output = MagicMock()
        mock_agent_output.result.error = None

        await configure_evaluation_span(
            span=span,  # type: ignore[arg-type]
            evaluation_run_results=mock_evaluation_run_results,
            execution_id="eval-complete",
            agent_execution_output=mock_agent_output,
        )

        # Verify score calculation
        output_data = json.loads(span.attributes["output"])
        assert output_data["score"] == 80  # (70 + 90) / 2

        # Verify metadata
        assert span.attributes["agentId"] == "eval-complete"

        # Verify status is OK (no error)
        assert span._status is not None
        assert span._status.status_code == StatusCode.OK

    @pytest.mark.asyncio
    async def test_configure_evaluation_span_with_error(self):
        """Test configuring evaluation span with agent error."""
        span = MockSpan()

        mock_evaluation_run_results = MagicMock()
        mock_evaluation_run_results.evaluation_run_results = []

        # Mock agent execution output with error
        mock_agent_output = MagicMock()
        mock_error = MagicMock()
        # Configure __str__ to return "Agent failed"
        mock_error.configure_mock(__str__=lambda self: "Agent failed")
        mock_agent_output.result.error = mock_error

        await configure_evaluation_span(
            span=span,  # type: ignore[arg-type]
            evaluation_run_results=mock_evaluation_run_results,
            execution_id="eval-error",
            agent_execution_output=mock_agent_output,
        )

        # Verify status is ERROR
        assert span._status is not None
        assert span._status.status_code == StatusCode.ERROR
        assert span._status.description is not None
        assert "Agent failed" in span._status.description

    @pytest.mark.asyncio
    async def test_configure_evaluation_span_without_agent_output(self):
        """Test configuring evaluation span without agent execution output."""
        span = MockSpan()

        mock_result = MagicMock()
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

    @pytest.mark.asyncio
    async def test_configure_evaluation_span_with_input_data(self):
        """Test configuring evaluation span with input data."""
        span = MockSpan()

        mock_result = MagicMock()
        mock_result.result.score = 75.0

        mock_evaluation_run_results = MagicMock()
        mock_evaluation_run_results.evaluation_run_results = [mock_result]

        input_data = {"a": 5, "b": 3, "operator": "+"}

        await configure_evaluation_span(
            span=span,  # type: ignore[arg-type]
            evaluation_run_results=mock_evaluation_run_results,
            execution_id="eval-with-input",
            input_data=input_data,
            agent_execution_output=None,
        )

        # Verify input data is set
        assert "input" in span.attributes
        input_data_parsed = json.loads(span.attributes["input"])
        assert input_data_parsed == {"a": 5, "b": 3, "operator": "+"}

        # Verify other attributes are also set
        assert "output" in span.attributes
        assert span.attributes["agentId"] == "eval-with-input"
        assert span._status is not None
        assert span._status.status_code == StatusCode.OK

    def test_set_evaluation_output_and_metadata_with_input_data(self):
        """Test setting evaluation span attributes with input data."""
        span = MockSpan()

        input_data = {"query": "test", "context": "example"}

        set_evaluation_output_and_metadata(
            span=span,  # type: ignore[arg-type]
            avg_score=92.0,
            execution_id="eval-input-test",
            input_data=input_data,
            has_error=False,
        )

        # Verify input is set
        assert "input" in span.attributes
        input_parsed = json.loads(span.attributes["input"])
        assert input_parsed == {"query": "test", "context": "example"}

        # Verify output is set
        output_data = json.loads(span.attributes["output"])
        assert output_data == {"score": 92}

        # Verify other attributes
        assert span.attributes["agentId"] == "eval-input-test"
