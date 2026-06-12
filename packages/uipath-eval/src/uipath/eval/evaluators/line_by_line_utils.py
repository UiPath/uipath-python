"""Utilities for line-by-line evaluation."""

from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from ..models import AgentExecution, EvaluationResult


def split_into_lines(
    text: Any, delimiter: str, target_output_key: str | None = None
) -> list[str]:
    """Split text into lines using the configured delimiter.

    Args:
        text: The text to split (can be str or dict)
        delimiter: The delimiter to split on
        target_output_key: Optional key to extract from dict before splitting

    Returns:
        List of lines (empty lines filtered out)
    """
    # Handle dict case (when target_output_key is provided and != "*")
    if target_output_key and target_output_key != "*":
        if isinstance(text, dict) and target_output_key in text:
            text = text[target_output_key]

    # Convert to string if needed
    if not isinstance(text, str):
        text = str(text)

    # Split by delimiter and filter empty lines
    lines = text.split(delimiter)
    return [line for line in lines if line.strip()]


def wrap_line_in_structure(
    line: str, target_output_key: str | None = None
) -> str | dict[str, str]:
    """Wrap a line in the appropriate structure based on target_output_key.

    Args:
        line: The line to wrap
        target_output_key: The target output key (use "*" or None for no wrapping)

    Returns:
        Either the line directly (if "*") or wrapped in a dict
    """
    if not target_output_key or target_output_key == "*":
        return line
    return {target_output_key: line}


def aggregate_line_scores(line_results: list[tuple[int, Any]]) -> float:
    """Aggregate scores from line evaluation results.

    Args:
        line_results: List of (line_number, result) tuples

    Returns:
        Average score across all lines
    """
    if not line_results:
        return 0.0

    scores = []
    for _line_num, result in line_results:
        if hasattr(result, "score"):
            score = result.score
            # Convert boolean to float
            if isinstance(score, bool):
                scores.append(1.0 if score else 0.0)
            else:
                scores.append(float(score))

    return sum(scores) / len(scores) if scores else 0.0


async def evaluate_lines(
    actual_lines: list[str],
    expected_lines: list[str],
    target_output_key: str,
    agent_execution: "AgentExecution",
    evaluate_fn: Callable[[Any, Any], Any],
    create_line_criteria_fn: Callable[[str], Any],
) -> tuple[list[Any], list[tuple[int, "EvaluationResult"]]]:
    """Evaluate each line and return details and results.

    Args:
        actual_lines: List of actual output lines
        expected_lines: List of expected output lines
        target_output_key: Key for wrapping lines
        agent_execution: Original agent execution
        evaluate_fn: Function to evaluate (line_execution, line_criteria) -> result
        create_line_criteria_fn: Function to create criteria for a line (expected_line) -> criteria

    Returns:
        Tuple of (line_details, line_results)
    """
    # Import here to avoid circular dependency
    from .output_evaluator import LineEvaluationDetail

    line_details = []
    line_results: list[tuple[int, Any]] = []
    max_lines = max(len(actual_lines), len(expected_lines))

    for i in range(max_lines):
        actual_line = actual_lines[i] if i < len(actual_lines) else ""
        expected_line = expected_lines[i] if i < len(expected_lines) else ""

        # Wrap lines in the same structure as original output
        line_agent_output = wrap_line_in_structure(actual_line, target_output_key)

        # Create a modified agent execution for this line
        from ..models.models import AgentExecution

        line_agent_execution = AgentExecution(
            agent_input=agent_execution.agent_input,
            agent_output=line_agent_output,
            agent_trace=agent_execution.agent_trace,
            expected_agent_behavior=getattr(
                agent_execution, "expected_agent_behavior", None
            ),
            simulation_instructions=getattr(
                agent_execution, "simulation_instructions", ""
            ),
        )

        # Create criteria for this line using the provided function
        line_criteria = create_line_criteria_fn(expected_line)

        # Evaluate this line
        line_result = await evaluate_fn(line_agent_execution, line_criteria)

        # Store line evaluation detail
        score_value = line_result.score if hasattr(line_result, "score") else 0.0
        line_details.append(
            LineEvaluationDetail(
                line_number=i + 1,
                actual=actual_line,
                expected=expected_line,
                score=score_value,
                details=line_result.details
                if hasattr(line_result, "details")
                else None,
            )
        )

        # Store for runtime extraction
        line_results.append((i + 1, line_result))

    return line_details, line_results


def build_line_by_line_result(
    line_details: list[Any],
    line_results: list[tuple[int, Any]],
    actual_lines: list[str],
    expected_lines: list[str],
) -> Any:
    """Build the final aggregated result with line-by-line details.

    Args:
        line_details: List of LineEvaluationDetail objects
        line_results: List of (line_number, result) tuples
        actual_lines: Original actual lines
        expected_lines: Original expected lines

    Returns:
        NumericEvaluationResult with line-by-line details attached
    """
    from ..models.models import NumericEvaluationResult
    from .output_evaluator import (
        AggregationMethod,
        LineByLineEvaluationDetails,
        LineByLineEvaluationResult,
    )

    # Calculate aggregate score
    aggregated_score = aggregate_line_scores(line_results)

    # Create aggregated details
    details = LineByLineEvaluationDetails(
        line_by_line_results=line_details,
        total_lines_actual=len(actual_lines),
        total_lines_expected=len(expected_lines),
        aggregation_method=AggregationMethod.AVERAGE,
    )

    # Create the aggregated result
    aggregated_result = NumericEvaluationResult(
        score=aggregated_score,
        details=details,
    )

    # Attach line results container for runtime to extract
    setattr(  # noqa: B010
        aggregated_result,
        "_line_by_line_results",
        LineByLineEvaluationResult(
            line_results=line_results, aggregation_method=AggregationMethod.AVERAGE
        ),
    )

    return aggregated_result
