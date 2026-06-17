"""Exact match evaluator for binary pass/fail evaluation of agent outputs."""

import json

from pydantic import Field

from uipath.eval.models import BooleanEvaluationResult, EvaluationResult

from .._helpers.output_path import resolve_output_path
from ..models.models import AgentExecution
from ._aggregators import AggregatorSpec
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
    """

    # Optional run-level aggregator config (e.g. a classification aggregator with a
    # fixed class set). The evaluator does no per-datapoint aggregation; it only
    # forwards this config into the per-datapoint justification so the downstream
    # C# post-pass can build a confusion matrix + P/R/F1 across the dataset.
    # Deserialized from the legacy evaluator JSON's top-level `aggregators` key.
    aggregators: list[AggregatorSpec] | None = Field(default=None, alias="aggregators")

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
            EvaluationResult: Boolean result. When `aggregators` is configured, the
            result's `details` carries a JSON string of {expected, actual, aggregators}
            so the C# post-pass can discover aggregator config and the expected label
            per datapoint.
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

        # Legacy evaluators use a `str` justification (generic J = str). Emit a JSON
        # string directly — _serialize_justification passes strings through unchanged,
        # so this lands verbatim in EvalScore.Justification on the C# side.
        details: str | None = None
        if self.aggregators:
            details = json.dumps(
                {
                    "expected": str(expected_output),
                    "actual": str(actual_output),
                    "aggregators": [
                        spec.model_dump(by_alias=True) for spec in self.aggregators
                    ],
                }
            )

        return BooleanEvaluationResult(score=is_match, details=details)
