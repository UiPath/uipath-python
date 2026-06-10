"""Exact match evaluator for agent outputs."""

from typing import Any

from pydantic import Field

from ..models import (
    AgentExecution,
    EvaluationResult,
    EvaluatorType,
    NumericEvaluationResult,
)
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

    # Run-level aggregator policies authored on this evaluator in the UI.
    # Each entry is an AggregatorConfig-shaped dict (function + optional
    # classes / average / beta). When empty/absent, no aggregation runs for
    # this evaluator — the runs-table chip shows the existing pass-rate.
    aggregators: list[dict[str, Any]] = Field(default_factory=list)


class ExactMatchJustification(BaseEvaluatorJustification):
    """ExactMatch's per-datapoint justification.

    Carries the standard `expected` / `actual` plus an `aggregators` field that
    declares the run-level aggregations this evaluator type produces (precision
    / recall / F1, macro averaging). The cloud aggregate-only post-pass
    (`uipath eval --aggregate-only`) harvests both the observations and the
    per-evaluator aggregator policy from the same data path.
    """

    aggregators: list[dict[str, Any]] = []


class ExactMatchEvaluator(
    OutputEvaluator[
        OutputEvaluationCriteria, ExactMatchEvaluatorConfig, ExactMatchJustification
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
        agent_execution: AgentExecution,
        evaluation_criteria: OutputEvaluationCriteria,
    ) -> EvaluationResult:
        """Evaluate whether actual output exactly matches expected output.

        Returns:
            EvaluationResult: Boolean result indicating exact match (True/False).
            The justification carries `expected` / `actual` so an aggregator
            post-pass can pick up the observation without re-reading the eval set.
        """
        actual_output = self._get_actual_output(agent_execution)
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
                "aggregators": self.evaluator_config.aggregators,
            }
        )
        return NumericEvaluationResult(
            score=float(is_exact_match),
            details=validated_justification,
        )
