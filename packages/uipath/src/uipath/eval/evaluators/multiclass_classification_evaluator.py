"""Multiclass classification evaluator for agent outputs.

Evaluates multiclass classification by comparing predicted vs expected class.
Per-datapoint score is 1.0 (correct) or 0.0 (incorrect). The reduce_scores
method reads predicted/expected from justification details to reconstruct a
confusion matrix and compute precision, recall, or F-score with micro or
macro averaging.
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


class MulticlassClassificationEvaluationCriteria(BaseEvaluationCriteria):
    """Per-datapoint criteria: which class this sample should belong to."""

    expected_class: str


class MulticlassClassificationEvaluatorConfig(
    OutputEvaluatorConfig[MulticlassClassificationEvaluationCriteria]
):
    """Configuration for the multiclass classification evaluator."""

    name: str = "MulticlassClassificationEvaluator"
    classes: list[str]
    metric_type: Literal["precision", "recall", "f-score"] = "f-score"
    averaging: Literal["micro", "macro"] = "macro"
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
    ) -> "MulticlassClassificationEvaluatorConfig":
        """Reject aggregators that are inconsistent with the evaluator's own config.

        Two checks:
          * Every evaluator-level class must appear in every aggregator's
            ``classes`` list (case-insensitive). Otherwise the per-datapoint
            and aggregator paths score disjoint label spaces.
          * For each aggregator whose ``type`` matches the evaluator-level
            ``metric_type`` (mapped via :data:`_METRIC_TYPE_TO_AGGREGATOR_TYPE`),
            the aggregator's ``averaging`` must match the evaluator's
            ``averaging``, and for ``fscore`` the ``f_value`` must match too.
            Otherwise the per-evaluator headline and the dataset evaluator's
            per-aggregator score diverge silently.
        """
        if not self.aggregators:
            return self
        evaluator_classes_lower = {c.lower() for c in self.classes}
        evaluator_aggregator_type = _METRIC_TYPE_TO_AGGREGATOR_TYPE.get(
            self.metric_type
        )
        for spec in self.aggregators:
            spec_classes_lower = {c.lower() for c in spec.classes}
            missing = evaluator_classes_lower - spec_classes_lower
            if missing:
                raise ValueError(
                    f"Aggregator '{spec.type}' on evaluator '{self.name}' "
                    f"declares classes={spec.classes!r} but the evaluator's "
                    f"classes={self.classes!r} include {sorted(missing)!r} "
                    "that the aggregator does not. Aggregators must cover "
                    "the evaluator's full class space."
                )
            if spec.type == evaluator_aggregator_type:
                if spec.averaging != self.averaging:
                    raise ValueError(
                        f"Aggregator '{spec.type}' on evaluator '{self.name}' "
                        f"has averaging={spec.averaging!r} but the evaluator's "
                        f"averaging={self.averaging!r}. The per-evaluator "
                        "headline and the aggregator would compute different "
                        "scores."
                    )
                if (
                    isinstance(spec, FScoreAggregatorSpec)
                    and spec.f_value != self.f_value
                ):
                    raise ValueError(
                        f"Aggregator 'fscore' on evaluator '{self.name}' has "
                        f"f_value={spec.f_value} but the evaluator's f_value="
                        f"{self.f_value}. The per-evaluator headline and the "
                        "aggregator would compute different F-beta scores."
                    )
        return self


class MulticlassClassificationEvaluator(
    BaseOutputEvaluator[
        MulticlassClassificationEvaluationCriteria,
        MulticlassClassificationEvaluatorConfig,
        BaseEvaluatorJustification,
    ]
):
    """Multiclass classification evaluator with micro/macro averaging.

    Per-datapoint scores are 1.0 (correct) or 0.0 (incorrect). The reduce_scores
    method reads predicted/expected from justification details to reconstruct the
    confusion matrix and compute the configured metric.
    """

    @classmethod
    def get_evaluator_id(cls) -> str:
        """Get the evaluator id."""
        return EvaluatorType.MULTICLASS_CLASSIFICATION.value

    async def evaluate(
        self,
        agent_execution: AgentExecution,
        evaluation_criteria: MulticlassClassificationEvaluationCriteria,
    ) -> EvaluationResult:
        """Evaluate multiclass classification by comparing predicted vs expected class.

        Configuration errors (e.g. ``expected_class`` not in the configured
        ``classes``) raise — that's a setup mistake the user must fix. But a
        predicted class outside the vocabulary (a sloppy LLM returning
        "unknown", garbage, or an unconfigured label) returns a 0.0 score with
        the OOV label preserved in the justification, mirroring the binary
        evaluator's behavior. The dataset evaluator's confusion matrix
        accounts for these via ``n_skipped``.
        """
        predicted_class = str(self._get_actual_output(agent_execution)).lower()
        expected_class = evaluation_criteria.expected_class.lower()
        classes = [c.lower() for c in self.evaluator_config.classes]

        if expected_class not in classes:
            raise UiPathEvaluationError(
                code="INVALID_EXPECTED_CLASS",
                title="Expected class not in configured classes",
                detail=f"Expected class '{expected_class}' is not in the configured classes: {classes}",
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
        """Reconstruct confusion matrix from details and compute the configured metric."""
        if not results:
            return 0.0

        classes = [c.lower() for c in self.evaluator_config.classes]
        k = len(classes)
        metric_type = self.evaluator_config.metric_type
        averaging = self.evaluator_config.averaging
        f_value = self.evaluator_config.f_value

        # Reconstruct confusion matrix: confusion[pred_idx][exp_idx]
        confusion = [[0] * k for _ in range(k)]
        for r in results:
            details = BaseEvaluatorJustification.try_from(r.details)
            if details is None:
                continue
            pred = details.actual
            exp = details.expected
            if pred in classes and exp in classes:
                confusion[classes.index(pred)][classes.index(exp)] += 1

        if averaging == "micro":
            return _micro_metric(confusion, k, metric_type, f_value)
        else:
            return _macro_metric(confusion, k, metric_type, f_value)


def _micro_metric(
    confusion: list[list[int]],
    k: int,
    metric_type: str,
    f_value: float,
) -> float:
    """Compute micro-averaged metric from confusion matrix."""
    total_tp = sum(confusion[i][i] for i in range(k))
    # For micro-averaging, sum TP/FP/FN across all classes
    total_fp = sum(
        sum(confusion[i][j] for j in range(k)) - confusion[i][i] for i in range(k)
    )
    total_fn = sum(
        sum(confusion[j][i] for j in range(k)) - confusion[i][i] for i in range(k)
    )

    if metric_type == "precision":
        denom = total_tp + total_fp
        return total_tp / denom if denom > 0 else 0.0
    elif metric_type == "recall":
        denom = total_tp + total_fn
        return total_tp / denom if denom > 0 else 0.0
    elif metric_type == "f-score":
        p = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
        rec = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
        beta_sq = f_value**2
        f_denom = beta_sq * p + rec
        return (1 + beta_sq) * p * rec / f_denom if f_denom > 0 else 0.0
    return 0.0


def _macro_metric(
    confusion: list[list[int]],
    k: int,
    metric_type: str,
    f_value: float,
) -> float:
    """Compute macro-averaged metric from confusion matrix."""
    per_class_metrics: list[float] = []

    for c in range(k):
        tp = confusion[c][c]
        fp = sum(confusion[c][j] for j in range(k)) - tp
        fn = sum(confusion[j][c] for j in range(k)) - tp

        if metric_type == "precision":
            denom = tp + fp
            per_class_metrics.append(tp / denom if denom > 0 else 0.0)
        elif metric_type == "recall":
            denom = tp + fn
            per_class_metrics.append(tp / denom if denom > 0 else 0.0)
        elif metric_type == "f-score":
            p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            beta_sq = f_value**2
            f_denom = beta_sq * p + rec
            f_score = (1 + beta_sq) * p * rec / f_denom if f_denom > 0 else 0.0
            per_class_metrics.append(f_score)

    if not per_class_metrics:
        return 0.0
    return sum(per_class_metrics) / len(per_class_metrics)
