"""Exact match evaluator for binary pass/fail evaluation of agent outputs."""

import json
from typing import Any, Optional

from pydantic import Field

from uipath.eval.models import BooleanEvaluationResult, EvaluationResult

from .._helpers.output_path import resolve_output_path
from ..models.models import AgentExecution
from .base_legacy_evaluator import LegacyEvaluationCriteria, LegacyEvaluatorConfig
from .legacy_deterministic_evaluator_base import BaseLegacyDeterministicEvaluator


class LegacyExactMatchEvaluatorConfig(LegacyEvaluatorConfig):
    """Configuration for legacy exact-match evaluators."""

    name: str = "LegacyExactMatchEvaluator"


class LegacyExactMatchEvaluator(
    BaseLegacyDeterministicEvaluator[LegacyExactMatchEvaluatorConfig]
):
    """Evaluator that performs exact structural matching between expected and actual outputs.

    This evaluator returns True if the actual output exactly matches the expected output
    after canonical JSON normalization, and False otherwise. Numbers are normalized
    to floats for consistent comparison.

    The evaluator always emits a `details` JSON string carrying `{expected, actual,
    aggregators}`. `aggregators` is the per-evaluator policy the user authored
    in the UI (zero or more of precision / recall / fscore). The cloud V3
    post-pass (`uipath eval --aggregate-only`) harvests both the observations
    and the policy from the same data path; the runs-table chip renders one
    pill per aggregator in place of the pass-rate. Travels via
    `EvalScore.Justification` (low-code) / `EvaluatorRun.Result.Score.
    Justification` (coded) in C# without requiring any side-channel config.
    """

    # Run-level aggregator policies authored on this evaluator in the UI.
    # Loaded from the evaluator JSON file via Pydantic alias. Each entry is
    # an AggregatorConfig-shaped dict (function + optional classes/average/
    # beta). When empty/absent, no aggregation runs for this evaluator —
    # the runs-table chip shows the existing pass-rate.
    aggregators: list[dict[str, Any]] = Field(default_factory=list)

    async def evaluate(
        self,
        agent_execution: AgentExecution,
        evaluation_criteria: LegacyEvaluationCriteria,
    ) -> EvaluationResult:
        """Evaluate whether actual output exactly matches expected output.

        Args:
            agent_execution: The execution details containing:
                - agent_input: The input received by the agent
                - actual_output: The actual output from the agent
                - spans: The execution spans to use for the evaluation
            evaluation_criteria: The criteria to evaluate

        Returns:
            EvaluationResult: Boolean result with a `details` JSON string
            of `{"expected": ..., "actual": ...}` so a post-pass aggregator
            can pick up the observation without re-reading the eval set.
        """
        actual_output = agent_execution.agent_output
        expected_output = evaluation_criteria.expected_output

        if self.target_output_key and self.target_output_key != "*":
            if isinstance(actual_output, dict) and isinstance(expected_output, dict):
                actual_resolved = True
                expected_resolved = True

                try:
                    actual_output = resolve_output_path(
                        actual_output, self.target_output_key
                    )
                except (KeyError, IndexError, TypeError):
                    actual_resolved = False

                try:
                    expected_output = resolve_output_path(
                        expected_output, self.target_output_key
                    )
                except (KeyError, IndexError, TypeError):
                    expected_resolved = False

                if not actual_resolved or not expected_resolved:
                    actual_output = expected_output = {}

        is_match = self._canonical_json(actual_output) == self._canonical_json(
            expected_output
        )

        details: Optional[str] = json.dumps(
            {
                "expected": str(expected_output),
                "actual": str(actual_output),
                "aggregators": self.aggregators,
            }
        )
        return BooleanEvaluationResult(score=is_match, details=details)
