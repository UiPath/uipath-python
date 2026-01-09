"""Utility functions for setting evaluation span attributes."""

import json
from typing import Any, Dict, Optional

from opentelemetry.trace import Span, Status, StatusCode
from pydantic import BaseModel, ConfigDict, Field

# Type hint for runtime protocol (avoids circular imports)
try:
    from uipath.runtime import UiPathRuntimeProtocol
except ImportError:
    UiPathRuntimeProtocol = Any  # type: ignore


class EvalSetRunOutput(BaseModel):
    """Output model for Evaluation Set Run span."""

    model_config = ConfigDict(populate_by_name=True)

    score: int = Field(..., alias="score")


class EvaluationOutput(BaseModel):
    """Output model for Evaluation span."""

    model_config = ConfigDict(populate_by_name=True)

    score: int = Field(..., alias="score")


class EvaluationOutputSpanOutput(BaseModel):
    """Output model for Evaluation output span."""

    model_config = ConfigDict(populate_by_name=True)

    type: int = Field(1, alias="type")
    value: float = Field(..., alias="value")
    evaluator_id: Optional[str] = Field(None, alias="evaluatorId")
    justification: Optional[str] = Field(None, alias="justification")


def calculate_overall_score(evaluator_averages: Dict[str, float]) -> float:
    """Calculate overall average score from evaluator averages.

    Args:
        evaluator_averages: Dictionary mapping evaluator IDs to their average scores

    Returns:
        Overall average score across all evaluators, or 0.0 if no evaluators
    """
    if not evaluator_averages:
        return 0.0
    return sum(evaluator_averages.values()) / len(evaluator_averages)


def calculate_evaluation_average_score(evaluation_run_results: Any) -> float:
    """Calculate average score from evaluation run results.

    Args:
        evaluation_run_results: EvaluationRunResult object containing evaluation results

    Returns:
        Average score across all evaluators, or 0.0 if no results
    """
    if not evaluation_run_results.evaluation_run_results:
        return 0.0

    total_score = sum(
        result.result.score for result in evaluation_run_results.evaluation_run_results
    )
    return total_score / len(evaluation_run_results.evaluation_run_results)


def set_eval_set_run_output_and_metadata(
    span: Span,
    overall_score: float,
    execution_id: str,
    input_schema: Optional[Dict[str, Any]],
    output_schema: Optional[Dict[str, Any]],
    success: bool = True,
) -> None:
    """Set output and metadata attributes for Evaluation Set Run span.

    Args:
        span: The OpenTelemetry span to set attributes on
        overall_score: The overall average score across all evaluators
        execution_id: The execution ID for the evaluation set run
        input_schema: The input schema from the runtime
        output_schema: The output schema from the runtime
        success: Whether the evaluation set run was successful
    """
    # Set span output with overall score using Pydantic model (formatted for UI rendering)
    output = EvalSetRunOutput(score=int(overall_score))
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
    avg_score: float,
    execution_id: str,
    input_data: Optional[Dict[str, Any]] = None,
    has_error: bool = False,
    error_message: Optional[str] = None,
) -> None:
    """Set output and metadata attributes for Evaluation span.

    Args:
        span: The OpenTelemetry span to set attributes on
        avg_score: The average score for this evaluation across all evaluators
        execution_id: The execution ID for this evaluation
        input_data: The input data for this evaluation
        has_error: Whether the evaluation had an error
        error_message: Optional error message if has_error is True
    """
    # Set span output with average score using Pydantic model (formatted for UI rendering)
    output = EvaluationOutput(score=int(avg_score))
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
        score: The evaluation score
        evaluator_id: The ID of the evaluator that produced this score
        justification: Optional justification text for the score
    """
    # Set output using Pydantic model (formatted for UI rendering)
    output = EvaluationOutputSpanOutput(
        value=score,
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
    runtime: Any,
    get_schema_func: Any,
    success: bool = True,
) -> None:
    """Configure Evaluation Set Run span with output and metadata.

    This high-level function handles:
    - Calculating overall score from evaluator averages
    - Getting runtime schemas
    - Setting all span attributes

    Args:
        span: The OpenTelemetry span to configure
        evaluator_averages: Dictionary mapping evaluator IDs to their average scores
        execution_id: The execution ID for the evaluation set run
        runtime: The runtime instance
        get_schema_func: Async function to get schema from runtime
        success: Whether the evaluation set run was successful
    """
    # Calculate overall score
    overall_score = calculate_overall_score(evaluator_averages)

    # Get runtime schemas
    try:
        schema = await get_schema_func(runtime)
        input_schema = schema.input
        output_schema = schema.output
    except Exception:
        input_schema = None
        output_schema = None

    # Set span output and metadata
    set_eval_set_run_output_and_metadata(
        span=span,
        overall_score=overall_score,
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
    - Calculating average score from evaluation results
    - Determining error status
    - Setting all span attributes

    Args:
        span: The OpenTelemetry span to configure
        evaluation_run_results: EvaluationRunResult object containing evaluation results
        execution_id: The execution ID for this evaluation
        input_data: The input data for this evaluation
        agent_execution_output: Optional agent execution output for error checking
    """
    # Calculate average score
    avg_score = calculate_evaluation_average_score(evaluation_run_results)

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
        avg_score=avg_score,
        execution_id=execution_id,
        input_data=input_data,
        has_error=has_error,
        error_message=error_message,
    )
