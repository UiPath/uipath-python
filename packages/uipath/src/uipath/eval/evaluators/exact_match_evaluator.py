"""Exact match evaluator for agent outputs."""

from ..models import (
    AgentExecution,
    EvaluationResult,
    EvaluatorType,
    NumericEvaluationResult,
)
from ._aggregators import AggregatorSpec
from .base_evaluator import BaseEvaluatorJustification
from .output_evaluator import (
    OutputEvaluationCriteria,
    OutputEvaluator,
    OutputEvaluatorConfig,
)


class ExactMatchEvaluatorConfig(OutputEvaluatorConfig[OutputEvaluationCriteria]):
    """Configuration for the exact match evaluator.

    The optional `aggregators` field attaches run-level aggregators (e.g. a
    classification aggregator with a fixed class set) that the downstream
    backend will compute after the eval set finishes. The Python runtime
    itself only forwards `aggregators` into the per-datapoint justification
    so the C# layer can pick it up; no per-datapoint math happens here.
    """

    name: str = "ExactMatchEvaluator"
    case_sensitive: bool = False
    negated: bool = False
    aggregators: list[AggregatorSpec] | None = None


class ExactMatchJustification(BaseEvaluatorJustification):
    """ExactMatch's per-datapoint justification.

    Carries the standard `expected` / `actual` plus the run-level
    `aggregators` config inlined per datapoint. The aggregators value is
    identical across datapoints — it's repeated only so the downstream
    consumer (the C# post-pass) can discover aggregator configuration from
    per-datapoint records without needing access to evaluator snapshots.
    Omitted entirely when no aggregators are configured.
    """

    aggregators: list[AggregatorSpec] | None = None


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
            The justification embeds the configured `aggregators` list so the
            downstream C# post-pass can discover aggregator configuration
            per datapoint.
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

        justification_payload: dict[str, object] = {
            "expected": str(expected_output),
            "actual": str(actual_output),
        }
        if self.evaluator_config.aggregators:
            # Pydantic models serialize via their parent BaseModel; embed as dicts
            # so the wire shape is JSON-friendly and readable from C#.
            justification_payload["aggregators"] = [
                spec.model_dump(by_alias=True) if hasattr(spec, "model_dump") else spec
                for spec in self.evaluator_config.aggregators
            ]

        validated_justification = self.validate_justification(justification_payload)
        return NumericEvaluationResult(
            score=float(is_exact_match),
            details=validated_justification,
        )
