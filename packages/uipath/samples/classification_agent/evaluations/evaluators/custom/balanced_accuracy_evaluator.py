"""Balanced accuracy evaluator — custom evaluator with non-trivial score aggregation.

Balanced accuracy = mean of per-class recall rates.

Per-datapoint scores encode class weights:
  - correct prediction: score = 1 / (num_classes * class_count_for_expected)
  - wrong prediction:   score = 0

Then reduce_scores sums the scores, which yields:
  sum = Σ_k (correct_k / (K * n_k)) = (1/K) Σ_k (correct_k / n_k) = balanced_accuracy
"""

from uipath.eval.evaluators.base_evaluator import (
    BaseEvaluationCriteria,
    BaseEvaluatorJustification,
)
from uipath.eval.evaluators.output_evaluator import (
    BaseOutputEvaluator,
    OutputEvaluatorConfig,
)
from uipath.eval.models import (
    AgentExecution,
    EvaluationResult,
    NumericEvaluationResult,
)
from uipath.eval.models.models import (
    EvaluationResultDto,
    UiPathEvaluationError,
    UiPathEvaluationErrorCategory,
)


class BalancedAccuracyEvaluationCriteria(BaseEvaluationCriteria):
    """Per-datapoint criteria: which class this sample should belong to."""

    expected_class: str


class BalancedAccuracyEvaluatorConfig(
    OutputEvaluatorConfig[BalancedAccuracyEvaluationCriteria]
):
    """Evaluator config with class list and per-class sample counts."""

    name: str = "BalancedAccuracyEvaluator"
    classes: list[str]
    class_counts: dict[str, int]


class BalancedAccuracyJustification(BaseEvaluatorJustification):
    """Details about how this datapoint was scored."""

    predicted_class: str
    expected_class: str
    weight: float
    is_match: bool


class BalancedAccuracyEvaluator(
    BaseOutputEvaluator[
        BalancedAccuracyEvaluationCriteria,
        BalancedAccuracyEvaluatorConfig,
        BalancedAccuracyJustification,
    ]
):
    """Balanced accuracy: mean of per-class recall rates.

    Uses weighted per-datapoint scores so that reduce_scores = sum()
    gives the correct balanced accuracy.
    """

    @classmethod
    def get_evaluator_id(cls) -> str:
        """Get the evaluator id."""
        return "custom-balanced-accuracy"

    @staticmethod
    def reduce_scores(results: list[EvaluationResultDto]) -> float:
        """Sum of pre-weighted scores = balanced accuracy."""
        return sum(r.score for r in results)

    async def evaluate(
        self,
        agent_execution: AgentExecution,
        evaluation_criteria: BalancedAccuracyEvaluationCriteria,
    ) -> EvaluationResult:
        predicted_class = str(self._get_actual_output(agent_execution)).lower()
        expected_class = evaluation_criteria.expected_class.lower()
        classes = [c.lower() for c in self.evaluator_config.classes]
        class_counts = {
            k.lower(): v for k, v in self.evaluator_config.class_counts.items()
        }

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

        num_classes = len(classes)
        n_k = class_counts.get(expected_class)
        if n_k is None or n_k <= 0:
            raise UiPathEvaluationError(
                code="INVALID_CLASS_COUNT",
                title="Missing or invalid class count",
                detail=f"class_counts must include a positive count for '{expected_class}'",
                category=UiPathEvaluationErrorCategory.USER,
            )

        weight = 1.0 / (num_classes * n_k)
        is_match = predicted_class == expected_class
        score = weight if is_match else 0.0

        justification = self.validate_justification(
            {
                "expected": expected_class,
                "actual": predicted_class,
                "predicted_class": predicted_class,
                "expected_class": expected_class,
                "weight": weight,
                "is_match": is_match,
            }
        )
        return NumericEvaluationResult(score=score, details=justification)
