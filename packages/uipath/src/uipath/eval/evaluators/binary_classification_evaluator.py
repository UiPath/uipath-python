"""Binary classification evaluator for agent outputs.

Evaluates binary classification by comparing predicted vs expected class.
Per-datapoint score is 1.0 (correct) or 0.0 (incorrect). The reduce_scores
method reads predicted/expected from justification details to build
TP/FP/FN/TN counts and compute precision, recall, or F-score.
"""

from typing import Literal

from pydantic import model_validator

from ..models import (
    AgentExecution,
    EvaluationResult,
    EvaluatorType,
    NumericEvaluationResult,
)
from ..models.models import (
    EvaluationResultDto,
    UiPathEvaluationError,
    UiPathEvaluationErrorCategory,
)
from ._aggregator_specs import AggregatorSpec, FScoreAggregatorSpec
from .base_evaluator import BaseEvaluationCriteria, BaseEvaluatorJustification
from .output_evaluator import (
    BaseOutputEvaluator,
    OutputEvaluatorConfig,
)

# Maps the evaluator-level ``metric_type`` strings to the corresponding
# aggregator-spec ``type`` values. The two spellings differ historically:
# the evaluator uses "f-score" (hyphen), the aggregator uses "fscore".
_METRIC_TYPE_TO_AGGREGATOR_TYPE = {
    "precision": "precision",
    "recall": "recall",
    "f-score": "fscore",
}


class BinaryClassificationEvaluationCriteria(BaseEvaluationCriteria):
    """Per-datapoint criteria: which class this sample should belong to."""

    expected_class: str


class BinaryClassificationEvaluatorConfig(
    OutputEvaluatorConfig[BinaryClassificationEvaluationCriteria]
):
    """Configuration for the binary classification evaluator."""

    name: str = "BinaryClassificationEvaluator"
    positive_class: str
    metric_type: Literal["precision", "recall", "f-score"] = "precision"
    f_value: float = 1.0
    # Optional run-level aggregators (precision / recall / fscore). Each is a
    # self-contained spec carrying its own ``classes``, ``averaging``, and
    # (for fscore) ``f_value``. The dataset-evaluator runtime walks this list
    # after all per-datapoint evaluators complete and emits one structured
    # result per aggregator keyed by ``{evaluator_name}.{aggregator.type}``.
    aggregators: list[AggregatorSpec] | None = None

    @model_validator(mode="after")
    def _validate_aggregators_against_evaluator_config(
        self,
    ) -> "BinaryClassificationEvaluatorConfig":
        """Reject aggregators that are inconsistent with the evaluator's own config.

        Two checks:
          * ``positive_class`` must appear in every aggregator's ``classes``
            list (case-insensitive). Otherwise the per-datapoint headline
            and the aggregator's confusion matrix score completely
            disjoint label spaces.
          * For each aggregator whose ``type`` matches the evaluator-level
            ``metric_type`` (mapped via :data:`_METRIC_TYPE_TO_AGGREGATOR_TYPE`),
            the aggregator's ``f_value`` must match the evaluator's
            ``f_value``. Otherwise the per-evaluator headline produced via
            ``reduce_scores`` and the dataset evaluator's per-aggregator
            score diverge silently.
        """
        if not self.aggregators:
            return self
        positive_lower = self.positive_class.lower() if self.positive_class else ""
        evaluator_aggregator_type = _METRIC_TYPE_TO_AGGREGATOR_TYPE.get(
            self.metric_type
        )
        for spec in self.aggregators:
            if positive_lower and positive_lower not in {
                c.lower() for c in spec.classes
            }:
                raise ValueError(
                    f"Aggregator '{spec.type}' on evaluator '{self.name}' "
                    f"declares classes={spec.classes!r} but positive_class="
                    f"{self.positive_class!r} is not in that list. Add the "
                    "positive class to the aggregator's classes or remove it."
                )
            if spec.type == evaluator_aggregator_type and isinstance(
                spec, FScoreAggregatorSpec
            ):
                if spec.f_value != self.f_value:
                    raise ValueError(
                        f"Aggregator 'fscore' on evaluator '{self.name}' has "
                        f"f_value={spec.f_value} but the evaluator's f_value="
                        f"{self.f_value}. The per-evaluator headline and the "
                        "aggregator would compute different F-beta scores."
                    )
        return self


class BinaryClassificationEvaluator(
    BaseOutputEvaluator[
        BinaryClassificationEvaluationCriteria,
        BinaryClassificationEvaluatorConfig,
        BaseEvaluatorJustification,
    ]
):
    """Binary classification evaluator with precision/recall/F-score aggregation.

    Per-datapoint scores are 1.0 (correct) or 0.0 (incorrect). The reduce_scores
    method reads predicted/expected from justification details to compute metrics.
    """

    @classmethod
    def get_evaluator_id(cls) -> str:
        """Get the evaluator id."""
        return EvaluatorType.BINARY_CLASSIFICATION.value

    async def evaluate(
        self,
        agent_execution: AgentExecution,
        evaluation_criteria: BinaryClassificationEvaluationCriteria,
    ) -> EvaluationResult:
        """Evaluate binary classification by comparing predicted vs expected class."""
        predicted_class = str(self._get_actual_output(agent_execution)).lower()
        expected_class = evaluation_criteria.expected_class.lower()
        positive_class = self.evaluator_config.positive_class.lower()

        if not positive_class:
            raise UiPathEvaluationError(
                code="INVALID_POSITIVE_CLASS",
                title="Positive class is empty",
                detail="positive_class must be a non-empty string",
                category=UiPathEvaluationErrorCategory.USER,
            )

        score = 1.0 if predicted_class == expected_class else 0.0

        justification = self.validate_justification(
            {
                "expected": expected_class,
                "actual": predicted_class,
            }
        )
        return NumericEvaluationResult(score=score, details=justification)

    def reduce_scores(self, results: list[EvaluationResultDto]) -> float:
        """Compute precision, recall, or F-score from per-datapoint results."""
        if not results:
            return 0.0

        positive_class = self.evaluator_config.positive_class.lower()
        tp = fp = fn = 0

        for r in results:
            details = BaseEvaluatorJustification.try_from(r.details)
            if details is None:
                continue
            pred = details.actual
            exp = details.expected
            if pred == positive_class and exp == positive_class:
                tp += 1
            elif pred == positive_class:
                fp += 1
            elif exp == positive_class:
                fn += 1

        metric_type = self.evaluator_config.metric_type

        if metric_type == "precision":
            return tp / (tp + fp) if (tp + fp) > 0 else 0.0
        elif metric_type == "recall":
            return tp / (tp + fn) if (tp + fn) > 0 else 0.0
        elif metric_type == "f-score":
            p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            beta_sq = self.evaluator_config.f_value**2
            denom = beta_sq * p + rec
            return (1 + beta_sq) * p * rec / denom if denom > 0 else 0.0
        else:
            return 0.0
