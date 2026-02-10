"""Utility functions for setting evaluation span attributes."""

import json
from typing import Any, Dict, Optional

from opentelemetry.trace import Span, Status, StatusCode
from pydantic import BaseModel, ConfigDict, Field

# Type hint for runtime protocol (avoids circular imports)
try:
    from uipath.runtime import UiPathRuntimeProtocol, UiPathRuntimeSchema
except ImportError:
    UiPathRuntimeProtocol = Any  # type: ignore


class EvalSetRunOutput(BaseModel):
    """Output model for Evaluation Set Run span."""

    model_config = ConfigDict(populate_by_name=True)

    scores: Dict[str, float] = Field(..., alias="scores")


class EvaluationOutput(BaseModel):
    """Output model for Evaluation span."""

    model_config = ConfigDict(populate_by_name=True)

    scores: Dict[str, float] = Field(..., alias="scores")


class EvaluationOutputSpanOutput(BaseModel):
    """Output model for Evaluation output span."""

    model_config = ConfigDict(populate_by_name=True)

    type: int = Field(1, alias="type")
    score: float = Field(..., alias="score")
    evaluator_id: Optional[str] = Field(None, alias="evaluatorId")
    justification: Optional[str] = Field(None, alias="justification")


def normalize_score_to_100(score: float) -> float:
    """Normalize score to 0-100 range.

    Args:
        score: Score value (can be 0-1 or 0-100)

    Returns:
        Score normalized to 0-100 range
    """
    # If score is between 0-1, scale to 0-100
    if 0 <= score <= 1:
        return round(score * 100, 2)
    # Otherwise assume it's already 0-100
    return round(min(max(score, 0), 100), 2)


def extract_evaluator_scores(evaluation_run_results: Any) -> Dict[str, float]:
    """Extract scores per evaluator from evaluation run results.

    Args:
        evaluation_run_results: EvaluationRunResult object containing evaluation results

    Returns:
        Dictionary mapping evaluator IDs to their normalized scores (0-100)
    """
    scores = {}
    if not evaluation_run_results.evaluation_run_results:
        return scores

    for result in evaluation_run_results.evaluation_run_results:
        evaluator_id = result.evaluator_id
        score = result.result.score
        scores[evaluator_id] = normalize_score_to_100(score)

    return scores


def set_eval_set_run_output_and_metadata(
    span: Span,
    evaluator_scores: Dict[str, float],
    execution_id: str,
    input_schema: Optional[Dict[str, Any]],
    output_schema: Optional[Dict[str, Any]],
    success: bool = True,
) -> None:
    """Set output and metadata attributes for Evaluation Set Run span.

    Args:
        span: The OpenTelemetry span to set attributes on
        evaluator_scores: Dictionary mapping evaluator IDs to their average scores (0-100)
        execution_id: The execution ID for the evaluation set run
        input_schema: The input schema from the runtime
        output_schema: The output schema from the runtime
        success: Whether the evaluation set run was successful
    """
    # Set span output with scores per evaluator using Pydantic model (formatted for UI rendering)
    output = EvalSetRunOutput(scores=evaluator_scores)
    span.set_attribute("output", output.model_dump_json(by_alias=True, indent=2))

    # Set metadata attributes
    span.set_attribute("agentId", execution_id)
    span.set_attribute("agentName", "N/A")

    # Set schemas as formatted JSON strings for proper rendering in UI
    if input_schema:
        try:
            span.set_attribute("inputSchema", json.dumps(input_schema, indent=2))
        except (TypeError, ValueError):
            span.set_attribute("inputSchema", "{}")
    else:
        span.set_attribute("inputSchema", "{}")

    if output_schema:
        try:
            span.set_attribute("outputSchema", json.dumps(output_schema, indent=2))
        except (TypeError, ValueError):
            span.set_attribute("outputSchema", "{}")
    else:
        span.set_attribute("outputSchema", "{}")

    # Set span status
    if success:
        span.set_status(Status(StatusCode.OK))


def set_evaluation_output_and_metadata(
    span: Span,
    evaluator_scores: Dict[str, float],
    execution_id: str,
    input_data: Optional[Dict[str, Any]] = None,
    has_error: bool = False,
    error_message: Optional[str] = None,
) -> None:
    """Set output and metadata attributes for Evaluation span.

    Args:
        span: The OpenTelemetry span to set attributes on
        evaluator_scores: Dictionary mapping evaluator IDs to their scores (0-100)
        execution_id: The execution ID for this evaluation
        input_data: The input data for this evaluation
        has_error: Whether the evaluation had an error
        error_message: Optional error message if has_error is True
    """
    # Set span output with scores per evaluator using Pydantic model (formatted for UI rendering)
    output = EvaluationOutput(scores=evaluator_scores)
    span.set_attribute("output", output.model_dump_json(by_alias=True, indent=2))

    # Set input data if provided (formatted JSON for UI rendering)
    if input_data is not None:
        try:
            span.set_attribute("input", json.dumps(input_data, indent=2))
        except (TypeError, ValueError):
            span.set_attribute("input", "{}")

    # Set metadata attributes
    span.set_attribute("agentId", execution_id)
    span.set_attribute("agentName", "N/A")

    # Set span status based on success
    if has_error and error_message:
        span.set_status(Status(StatusCode.ERROR, error_message))
    elif not has_error:
        span.set_status(Status(StatusCode.OK))


def set_evaluation_output_span_output(
    span: Span,
    score: float,
    evaluator_id: Optional[str] = None,
    justification: Optional[str] = None,
) -> None:
    """Set output attribute for Evaluation output span.

    Args:
        span: The OpenTelemetry span to set attributes on
        score: The evaluation score (0-100)
        evaluator_id: The ID of the evaluator that produced this score
        justification: Optional justification text for the score
    """
    # Normalize score to 0-100 range
    normalized_score = normalize_score_to_100(score)

    # Set output using Pydantic model (formatted for UI rendering)
    output = EvaluationOutputSpanOutput(
        score=normalized_score,
        evaluator_id=evaluator_id,
        justification=justification,
    )
    span.set_attribute(
        "output", output.model_dump_json(by_alias=True, exclude_none=True, indent=2)
    )


# High-level wrapper functions that handle complete flow


async def configure_eval_set_run_span(
    span: Span,
    evaluator_averages: Dict[str, float],
    execution_id: str,
    schema: UiPathRuntimeSchema,
    success: bool = True,
) -> None:
    """Configure Evaluation Set Run span with output and metadata.

    This high-level function handles:
    - Normalizing evaluator scores to 0-100 range
    - Getting runtime schemas
    - Setting all span attributes

    Args:
        span: The OpenTelemetry span to configure
        evaluator_averages: Dictionary mapping evaluator IDs to their average scores
        execution_id: The execution ID for the evaluation set run
        schema: The runtime schema
        success: Whether the evaluation set run was successful
    """
    # Normalize all scores to 0-100 range
    evaluator_scores = {
        evaluator_id: normalize_score_to_100(score)
        for evaluator_id, score in evaluator_averages.items()
    }

    # Get runtime schemas
    try:
        input_schema = schema.input
        output_schema = schema.output
    except Exception:
        input_schema = None
        output_schema = None

    # Set span output and metadata
    set_eval_set_run_output_and_metadata(
        span=span,
        evaluator_scores=evaluator_scores,
        execution_id=execution_id,
        input_schema=input_schema,
        output_schema=output_schema,
        success=success,
    )


async def configure_evaluation_span(
    span: Span,
    evaluation_run_results: Any,
    execution_id: str,
    input_data: Optional[Dict[str, Any]] = None,
    agent_execution_output: Optional[Any] = None,
) -> None:
    """Configure Evaluation span with output and metadata.

    This high-level function handles:
    - Extracting scores per evaluator from evaluation results
    - Normalizing scores to 0-100 range
    - Determining error status
    - Setting all span attributes

    Args:
        span: The OpenTelemetry span to configure
        evaluation_run_results: EvaluationRunResult object containing evaluation results
        execution_id: The execution ID for this evaluation
        input_data: The input data for this evaluation
        agent_execution_output: Optional agent execution output for error checking
    """
    # Extract evaluator scores (already normalized to 0-100)
    evaluator_scores = extract_evaluator_scores(evaluation_run_results)

    # Determine error status
    has_error = False
    error_message = None
    if agent_execution_output is not None:
        try:
            if agent_execution_output.result.error:
                has_error = True
                error_message = str(agent_execution_output.result.error)
        except (AttributeError, NameError, UnboundLocalError):
            pass

    # Set span output and metadata
    set_evaluation_output_and_metadata(
        span=span,
        evaluator_scores=evaluator_scores,
        execution_id=execution_id,
        input_data=input_data,
        has_error=has_error,
        error_message=error_message,
    )
