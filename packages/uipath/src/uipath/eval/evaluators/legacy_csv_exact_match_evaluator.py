"""CSV exact match evaluator for comparing specific columns in CSV outputs."""

import csv
import io
import json
from typing import Any

from pydantic import Field, field_validator

from uipath.eval.models import (
    BooleanEvaluationResult,
    EvaluationResult,
)

from ..models.models import AgentExecution
from .base_legacy_evaluator import LegacyEvaluationCriteria, LegacyEvaluatorConfig
from .legacy_deterministic_evaluator_base import BaseLegacyDeterministicEvaluator
from .line_by_line_utils import wrap_line_in_structure


class LegacyCSVExactMatchEvaluatorConfig(LegacyEvaluatorConfig):
    """Configuration for legacy CSV exact-match evaluators."""

    name: str = "LegacyCSVExactMatchEvaluator"


class LegacyCSVExactMatchEvaluator(
    BaseLegacyDeterministicEvaluator[LegacyCSVExactMatchEvaluatorConfig]
):
    """Evaluator that performs exact matching on specific columns in CSV outputs.

    This evaluator compares specific columns from actual and expected CSV outputs.
    It supports:
    - Multiple column comparison (comma-separated column names)
    - Case-insensitive column name matching
    - Job attachment inputs (automatic via base class)
    - Line-by-line evaluation (CSV-aware: preserves headers for each row)

    Line-by-line mode:
    When line_by_line_evaluation=True, the evaluator splits CSVs by line_delimiter
    and evaluates each data row separately. Headers from the first line are
    automatically prepended to each data row to create valid mini-CSVs.
    Results are aggregated using the average of all row scores.
    """

    target_sub_output_key: str = Field(
        ...,
        alias="targetSubOutputKey",
        description="Comma-separated list of column names to compare",
    )

    @field_validator("target_sub_output_key")
    @classmethod
    def validate_target_sub_output_key(cls, v: str) -> str:
        """Validate that target_sub_output_key is not empty."""
        if not v or not v.strip():
            raise ValueError("target_sub_output_key must not be empty")
        return v

    async def evaluate(
        self,
        agent_execution: AgentExecution,
        evaluation_criteria: LegacyEvaluationCriteria,
    ) -> EvaluationResult:
        """Evaluate whether specific CSV columns exactly match between actual and expected.

        Args:
            agent_execution: The execution details containing:
                - agent_input: The input received by the agent
                - agent_output: The actual output from the agent (can be CSV string or job attachment)
                - spans: The execution spans to use for the evaluation
            evaluation_criteria: The criteria to evaluate containing expected output

        Returns:
            EvaluationResult: Boolean result indicating whether the specified columns match

        Raises:
            ValueError: If CSV format is invalid or required columns are missing
        """
        # Get actual output (handles job attachments and target_output_key extraction)
        actual_output = self._get_actual_output(agent_execution)

        # Get expected output from criteria
        expected_output = evaluation_criteria.expected_output

        # Extract based on target_output_key if not wildcard
        if self.target_output_key and self.target_output_key != "*":
            if (
                isinstance(expected_output, dict)
                and self.target_output_key in expected_output
            ):
                expected_output = expected_output[self.target_output_key]

        # Extract CSV content from the outputs
        actual_csv = self._extract_csv_content(actual_output)
        expected_csv = self._extract_csv_content(expected_output)

        # Parse target columns
        target_columns = self._parse_target_columns(self.target_sub_output_key)

        # Extract column values from both CSVs
        actual_values = self._extract_single_record_from_csv(actual_csv, target_columns)
        expected_values = self._extract_single_record_from_csv(
            expected_csv, target_columns
        )

        # Compare values
        match = self._do_values_match(actual_values, expected_values)

        return BooleanEvaluationResult(score=match)

    def _extract_csv_content(self, output: Any) -> str:
        """Extract CSV content from various output formats.

        Args:
            output: The output value (can be string, dict with 'content' key, or other)

        Returns:
            CSV content as string

        Raises:
            ValueError: If output format is invalid or empty
        """
        csv_content = None

        # Handle dict with 'content' property
        if isinstance(output, dict):
            if "content" in output:
                csv_content = output["content"]
            else:
                # Try to serialize as JSON
                csv_content = json.dumps(output)
        # Handle string
        elif isinstance(output, str):
            csv_content = output
        else:
            # Try to convert to string
            csv_content = str(output)

        # Validate content is not empty
        if not csv_content or not csv_content.strip():
            raise ValueError("CSV output is null or empty")

        return csv_content

    def _parse_target_columns(self, target_sub_output_key: str) -> list[str]:
        """Parse comma-separated target columns.

        Args:
            target_sub_output_key: Comma-separated column names

        Returns:
            List of column names (trimmed and filtered)

        Raises:
            ValueError: If no valid columns are found
        """
        columns = [
            col.strip() for col in target_sub_output_key.split(",") if col.strip()
        ]

        if not columns:
            raise ValueError("At least one target column must be specified")

        return columns

    def _extract_single_record_from_csv(
        self, csv_content: str, target_columns: list[str]
    ) -> dict[str, str]:
        """Extract values for target columns from the first data row of CSV.

        Args:
            csv_content: The CSV content as string
            target_columns: List of column names to extract

        Returns:
            Dictionary mapping column names to values

        Raises:
            ValueError: If CSV format is invalid, headers missing, or columns not found
        """
        try:
            # Create CSV reader
            reader = csv.DictReader(io.StringIO(csv_content))

            # Get headers (field names)
            if reader.fieldnames is None:
                raise ValueError("CSV must contain headers")

            headers = reader.fieldnames

            # Create case-insensitive column mapping
            column_map = {h.lower(): h for h in headers}

            # Validate target columns exist (case-insensitive)
            missing_columns = []
            for col in target_columns:
                if col.lower() not in column_map:
                    missing_columns.append(col)

            if missing_columns:
                raise ValueError(f"Missing columns: {', '.join(missing_columns)}")

            # Read first data row
            try:
                row = next(reader)
            except StopIteration as e:
                raise ValueError("CSV must contain one data row") from e

            # Extract target column values
            result = {}
            for col in target_columns:
                actual_col_name = column_map[col.lower()]
                value = row.get(actual_col_name, "")
                # Trim whitespace from values
                result[col] = value.strip() if value else ""

            return result

        except csv.Error as e:
            raise ValueError(f"Invalid CSV format: {e}") from e

    def _do_values_match(
        self, actual_values: dict[str, str], expected_values: dict[str, str]
    ) -> bool:
        """Compare actual and expected values.

        Args:
            actual_values: Dictionary of actual column values
            expected_values: Dictionary of expected column values

        Returns:
            True if all values match exactly, False otherwise
        """
        for column, expected_value in expected_values.items():
            actual_value = actual_values.get(column)
            # Use exact string comparison (case-sensitive for values)
            if actual_value != expected_value:
                return False
        return True

    async def _evaluate_line_by_line(
        self,
        agent_execution: AgentExecution,
        evaluation_criteria: LegacyEvaluationCriteria,
    ) -> EvaluationResult:
        """Override line-by-line evaluation to handle CSV structure properly.

        For CSV files, we need to preserve headers when splitting into lines.
        This method:
        1. Extracts the CSV content (handles job attachments via _get_actual_output)
        2. Splits into header + data lines
        3. For each data line, creates a mini-CSV with header + that line
        4. Evaluates each mini-CSV
        5. Aggregates results

        Args:
            agent_execution: The execution details
            evaluation_criteria: The evaluation criteria

        Returns:
            NumericEvaluationResult with line-by-line details
        """
        # Import here to get NumericEvaluationResult
        from ..models.models import NumericEvaluationResult
        from .output_evaluator import (
            AggregationMethod,
            LineByLineEvaluationDetails,
            LineByLineEvaluationResult,
            LineEvaluationDetail,
        )

        # Get actual output (this handles job attachments automatically)
        actual_output = self._get_actual_output(agent_execution)

        # Get expected output from criteria
        expected_output = evaluation_criteria.expected_output

        # Extract based on target_output_key if not wildcard
        if self.target_output_key and self.target_output_key != "*":
            if (
                isinstance(expected_output, dict)
                and self.target_output_key in expected_output
            ):
                expected_output = expected_output[self.target_output_key]

        # Extract CSV content
        actual_csv = self._extract_csv_content(actual_output)
        expected_csv = self._extract_csv_content(expected_output)

        # Split into lines
        actual_lines = actual_csv.split(self.line_delimiter)
        expected_lines = expected_csv.split(self.line_delimiter)

        # Filter out empty lines
        actual_lines = [line for line in actual_lines if line.strip()]
        expected_lines = [line for line in expected_lines if line.strip()]

        # Validate we have at least headers
        if not actual_lines or not expected_lines:
            raise ValueError("CSV must contain at least a header row")

        # Extract headers (first line)
        actual_header = actual_lines[0]
        expected_header = expected_lines[0]

        # Get data rows (everything after first line)
        actual_data_rows = actual_lines[1:]
        expected_data_rows = expected_lines[1:]

        # Evaluate each line
        line_details = []
        line_results: list[tuple[int, Any]] = []
        max_lines = max(len(actual_data_rows), len(expected_data_rows))

        for i in range(max_lines):
            actual_line = actual_data_rows[i] if i < len(actual_data_rows) else ""
            expected_line = expected_data_rows[i] if i < len(expected_data_rows) else ""

            # Create mini-CSVs with header + data line
            if actual_line:
                actual_mini_csv = f"{actual_header}{self.line_delimiter}{actual_line}"
            else:
                actual_mini_csv = actual_header  # Just header, will fail validation

            if expected_line:
                expected_mini_csv = (
                    f"{expected_header}{self.line_delimiter}{expected_line}"
                )
            else:
                expected_mini_csv = expected_header  # Just header, will fail validation

            # Create a modified agent execution for this line
            line_agent_execution = AgentExecution(
                agent_input=agent_execution.agent_input,
                agent_output=wrap_line_in_structure(
                    actual_mini_csv, self.target_output_key
                ),
                agent_trace=agent_execution.agent_trace,
                expected_agent_behavior=getattr(
                    agent_execution, "expected_agent_behavior", None
                ),
                simulation_instructions=getattr(
                    agent_execution, "simulation_instructions", ""
                ),
            )

            # Create criteria for this line
            line_criteria = LegacyEvaluationCriteria(
                expected_output=wrap_line_in_structure(
                    expected_mini_csv, self.target_output_key
                ),
                expected_agent_behavior=evaluation_criteria.expected_agent_behavior,
            )

            # Evaluate this line
            try:
                line_result = await self.evaluate(line_agent_execution, line_criteria)
                score_value = (
                    line_result.score if hasattr(line_result, "score") else 0.0
                )
            except Exception:
                # If evaluation fails (e.g., missing data), score as 0
                line_result = BooleanEvaluationResult(score=False)
                score_value = 0.0

            # Store line evaluation detail
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

        # Calculate aggregate score
        scores = []
        for _line_num, result in line_results:
            if hasattr(result, "score"):
                score = result.score
                # Convert boolean to float
                if isinstance(score, bool):
                    scores.append(1.0 if score else 0.0)
                else:
                    scores.append(float(score))

        aggregated_score = sum(scores) / len(scores) if scores else 0.0

        # Create aggregated details
        details = LineByLineEvaluationDetails(
            line_by_line_results=line_details,
            total_lines_actual=len(actual_data_rows),
            total_lines_expected=len(expected_data_rows),
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
