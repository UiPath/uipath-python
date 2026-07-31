"""Exact match evaluator for workload outputs."""

from pydantic import Field, model_validator

from ..models import (
    EvaluationResult,
    EvaluatorType,
    NumericEvaluationResult,
    WorkloadExecution,
)
from ._aggregator_specs import AggregatorSpec
from .base_evaluator import BaseEvaluatorJustification
from .output_evaluator import (
    OutputEvaluationCriteria,
    OutputEvaluator,
    OutputEvaluatorConfig,
)


class ExactMatchEvaluatorConfig(OutputEvaluatorConfig[OutputEvaluationCriteria]):
    """Configuration for the exact match evaluator."""

    name: str = "ExactMatchEvaluator"
    case_sensitive: bool = False
    negated: bool = False
    classes: list[str] | None = Field(
        default=None,
        description=(
            "Label vocabulary shared by every aggregator on this evaluator. "
            "Labels are matched case-insensitively against the per-datapoint "
            "expected/actual outputs."
        ),
    )
    aggregators: list[AggregatorSpec] | None = Field(
        default=None,
        description=(
            "Dataset-level metrics (precision / recall / F-score / confusion "
            "matrix) computed over the per-datapoint match outcomes. Requires "
            "``classes``."
        ),
    )

    @model_validator(mode="after")
    def _validate_aggregators(self) -> "ExactMatchEvaluatorConfig":
        """Aggregators need a usable class vocabulary and per-label outcomes."""
        if not self.aggregators:
            return self
        if not self.classes:
            raise ValueError(
                f"ExactMatch evaluator '{self.name}' declares aggregators but no "
                "``classes`` list. Set ``classes`` to the label vocabulary the "
                "aggregators should compute Precision/Recall/F-score over."
            )
        if self.line_by_line_evaluator:
            raise ValueError(
                f"ExactMatch evaluator '{self.name}': aggregators are not "
                "supported with line_by_line_evaluator — per-line results carry "
                "no expected/actual labels, so every datapoint would be skipped."
            )
        if self.case_sensitive:
            raise ValueError(
                f"ExactMatch evaluator '{self.name}': aggregators are not "
                "supported with case_sensitive — the confusion matrix buckets "
                "labels case-insensitively, so a datapoint could score 0.0 yet "
                "land on the true-positive diagonal."
            )
        if self.negated:
            raise ValueError(
                f"ExactMatch evaluator '{self.name}': aggregators are not "
                "supported with negated — negation flips only the per-datapoint "
                "score, not the justification's expected/actual labels, so the "
                "confusion matrix would put matches on the true-positive diagonal "
                "while they scored 0.0 (and vice versa)."
            )
        lowered = [c.lower() for c in self.classes]
        if any(not c.strip() or c != c.strip() for c in self.classes) or len(
            set(lowered)
        ) != len(lowered):
            raise ValueError(
                f"ExactMatch evaluator '{self.name}': ``classes`` must be "
                "non-blank, have no leading/trailing whitespace, and be unique "
                "case-insensitively — labels are matched case-insensitively, so "
                "duplicates would collapse onto one matrix index, and padded "
                "labels would never match anything."
            )
        return self


class ExactMatchEvaluator(
    OutputEvaluator[
        OutputEvaluationCriteria, ExactMatchEvaluatorConfig, BaseEvaluatorJustification
    ]
):
    """Evaluator that performs exact structural matching between expected and actual outputs.

    This evaluator returns True if the actual output exactly matches the expected output
    after canonical JSON normalization, and False otherwise. Numbers are normalized
    to floats for consistent comparison.
    """

    @classmethod
    def get_evaluator_id(cls) -> str:
        """Get the evaluator id."""
        return EvaluatorType.EXACT_MATCH.value

    async def evaluate(
        self,
        workload_execution: WorkloadExecution,
        evaluation_criteria: OutputEvaluationCriteria,
    ) -> EvaluationResult:
        """Evaluate whether actual output exactly matches expected output.

        Args:
            workload_execution: The execution details containing:
                - agent_input: The input received by the agent
                - workload_output: The actual output from the agent
                - workload_trace: The execution spans to use for the evaluation
            evaluation_criteria: The criteria to evaluate

        Returns:
            EvaluationResult: Boolean result indicating exact match (True/False)
        """
        actual_output = self._get_actual_output(workload_execution)
        expected_output = self._get_expected_output(evaluation_criteria)

        if isinstance(actual_output, str) or isinstance(expected_output, str):
            actual_str = str(actual_output)
            expected_str = str(expected_output)
            if not self.evaluator_config.case_sensitive:
                actual_str = actual_str.lower()
                expected_str = expected_str.lower()
            is_exact_match = actual_str == expected_str
        else:
            is_exact_match = actual_output == expected_output

        if self.evaluator_config.negated:
            is_exact_match = not is_exact_match

        validated_justification = self.validate_justification(
            {
                "expected": str(expected_output),
                "actual": str(actual_output),
            }
        )
        return NumericEvaluationResult(
            score=float(is_exact_match),
            details=validated_justification,
        )
