"""Multiclass classification evaluator for agent outputs.

Evaluates multiclass classification by comparing predicted vs expected class.
Per-datapoint score is 1.0 (correct) or 0.0 (incorrect). The reduce_scores
method reads predicted/expected from justification details to reconstruct a
confusion matrix and compute precision, recall, or F-score with micro or
macro averaging.
"""

from typing import Literal

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
from .base_evaluator import BaseEvaluationCriteria, BaseEvaluatorJustification
from .output_evaluator import (
    BaseOutputEvaluator,
    OutputEvaluatorConfig,
)


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
        """Evaluate multiclass classification by comparing predicted vs expected class."""
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

        if predicted_class not in classes:
            raise UiPathEvaluationError(
                code="INVALID_PREDICTED_CLASS",
                title="Predicted class not in configured classes",
                detail=f"Predicted class '{predicted_class}' is not in the configured classes: {classes}",
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
            if isinstance(r.details, BaseEvaluatorJustification):
                details = r.details
            elif isinstance(r.details, dict):
                try:
                    details = BaseEvaluatorJustification.model_validate(r.details)
                except Exception:
                    continue
            else:
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
