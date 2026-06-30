from typing import List

from uipath.eval.evaluators import (
    BaseEvaluationCriteria,
    BaseEvaluator,
    BaseEvaluatorConfig,
    BaseEvaluatorJustification,
)
from uipath.eval.models import (
    EvaluationResult,
    NumericEvaluationResult,
    WorkloadExecution,
)


class CSVColumnsEvaluationCriteria(BaseEvaluationCriteria):
    """Evaluation criteria for the CSV columns evaluator."""

    expected_columns: List[str]


class CSVColumnsEvaluatorConfig(BaseEvaluatorConfig[CSVColumnsEvaluationCriteria]):
    """Configuration for the CSV columns evaluator."""

    name: str = "CSVColumnsEvaluator"
    default_evaluation_criteria: CSVColumnsEvaluationCriteria = (
        CSVColumnsEvaluationCriteria(expected_columns=[])
    )


class CSVColumnsEvaluator(
    BaseEvaluator[
        CSVColumnsEvaluationCriteria,
        CSVColumnsEvaluatorConfig,
        BaseEvaluatorJustification,
    ]
):
    """A custom evaluator that checks if the CSV column names are correctly identified."""

    @classmethod
    def get_evaluator_id(cls) -> str:
        return "CSVColumnsEvaluator"

    async def evaluate(
        self,
        workload_execution: WorkloadExecution,
        evaluation_criteria: CSVColumnsEvaluationCriteria,
    ) -> EvaluationResult:
        # Check if all expected columns are mentioned in the output
        # The agent writes: f"CSV shape {df.shape}\n\nCSV columns {df.columns}"

        columns_found = set()
        total_columns = len(evaluation_criteria.expected_columns)

        if total_columns == 0:
            return NumericEvaluationResult(
                score=1.0,
                details=self.validate_justification({"expected": "[]", "actual": "[]"}),
            )

        # Look for column names in agent traces (where print output is captured)
        for span in workload_execution.workload_trace:
            # Check span attributes
            if span.attributes:
                for attr_value in span.attributes.values():
                    if isinstance(attr_value, str):
                        for column in evaluation_criteria.expected_columns:
                            if column in attr_value:
                                columns_found.add(column)

            # Check span events (where stdout might be captured)
            if hasattr(span, "events") and span.events:
                for event in span.events:
                    if hasattr(event, "attributes") and event.attributes:
                        for attr_value in event.attributes.values():
                            if isinstance(attr_value, str):
                                for column in evaluation_criteria.expected_columns:
                                    if column in attr_value:
                                        columns_found.add(column)

        # Also check in the output
        if len(columns_found) < total_columns and workload_execution.workload_output:
            output_str = str(workload_execution.workload_output)
            for column in evaluation_criteria.expected_columns:
                if column in output_str:
                    columns_found.add(column)

        # Calculate score as ratio of found columns
        score = len(columns_found) / total_columns

        return NumericEvaluationResult(
            score=score,
            details=self.validate_justification(
                {
                    "expected": str(sorted(evaluation_criteria.expected_columns)),
                    "actual": str(sorted(columns_found)),
                }
            ),
        )
