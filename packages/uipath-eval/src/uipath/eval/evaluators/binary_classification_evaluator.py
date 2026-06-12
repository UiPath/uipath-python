"""Binary classification evaluator for agent outputs.

Evaluates binary classification by comparing predicted vs expected class.
Per-datapoint score is 1.0 (correct) or 0.0 (incorrect). The reduce_scores
method reads predicted/expected from justification details to build
TP/FP/FN/TN counts and compute precision, recall, or F-score.
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
