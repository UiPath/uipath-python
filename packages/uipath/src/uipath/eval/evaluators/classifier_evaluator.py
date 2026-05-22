"""Classification aggregator evaluator.

Pure-metadata evaluator: it carries a `classes` list and a `source_evaluator`
name, but does NOT compute classification metrics per datapoint. The actual
TP/TN/FP/FN tallying happens downstream (the C# layer in Studio Web reads the
agent output and the source evaluator's expected label, scans the output for
each configured class, and computes precision/recall/F-score after the
per-datapoint loop completes).

The per-datapoint `evaluate(...)` returns a sentinel score of 0.0 with a
ClassifierJustification payload. The payload survives the existing CLI →
backend wire path (via `_serialize_justification`) as a JSON-stringified
object, where the C# layer reads `classes` and `sourceEvaluator` from the
first per-datapoint result.
"""

from ..models import (
    AgentExecution,
    EvaluationResult,
    EvaluatorType,
    NumericEvaluationResult,
)
from .base_evaluator import (
    BaseEvaluationCriteria,
    BaseEvaluator,
    BaseEvaluatorConfig,
    BaseEvaluatorJustification,
)


class ClassifierEvaluationCriteria(BaseEvaluationCriteria):
    """Empty per-datapoint criteria for the classifier aggregator.

    The classifier has no per-datapoint config; this concrete subclass exists
    only because Pydantic's generic resolution requires a concrete (non-bound)
    type — using `BaseEvaluationCriteria` directly leaves T as `Any`.
    """

    pass


class ClassifierJustification(BaseEvaluatorJustification):
    """Metadata payload shipped per datapoint so the backend can read the classes list.

    Extends BaseEvaluatorJustification so the framework's J generic bound
    (`Union[str, BaseEvaluatorJustification]`) is satisfied; expected/actual
    are not meaningful for this evaluator and default to empty strings.
    """

    expected: str = ""
    actual: str = ""
    classes: list[str]
    source_evaluator: str


class ClassifierEvaluatorConfig(BaseEvaluatorConfig[ClassifierEvaluationCriteria]):
    """Configuration for the classification aggregator evaluator."""

    name: str = "ClassifierEvaluator"
    classes: list[str]
    source_evaluator: str
    default_evaluation_criteria: ClassifierEvaluationCriteria = (
        ClassifierEvaluationCriteria()
    )


class ClassifierEvaluator(
    BaseEvaluator[
        ClassifierEvaluationCriteria,
        ClassifierEvaluatorConfig,
        ClassifierJustification,
    ]
):
    """Carries the classes list to the backend; does no per-datapoint scoring.

    Add this to an evaluation set alongside the per-datapoint evaluator (e.g.
    ExactMatch) that produces expected/actual labels. The backend uses the
    classes list, the per-datapoint outputs, and the source evaluator's
    expected labels to build a confusion matrix + per-class metrics after the
    set finishes.
    """

    @classmethod
    def get_evaluator_id(cls) -> str:
        """Identifier matching the evaluatorTypeId discriminator on configs."""
        return EvaluatorType.CLASSIFIER.value

    async def evaluate(
        self,
        agent_execution: AgentExecution,
        evaluation_criteria: ClassifierEvaluationCriteria,
    ) -> EvaluationResult:
        """Return a sentinel per-datapoint result carrying the classes metadata.

        The score is fixed at 0.0 because this evaluator has no per-datapoint
        notion of pass/fail. Downstream code (the C# layer) ignores the score
        and reads `details.classes` + `details.source_evaluator` to drive the
        run-level classification math.
        """
        # agent_execution and evaluation_criteria intentionally unused; the
        # value of this evaluator is the config it carries, not any per-
        # datapoint computation. Touch them so linters don't flag.
        _ = agent_execution
        _ = evaluation_criteria

        return NumericEvaluationResult(
            score=0.0,
            details=ClassifierJustification(
                classes=list(self.evaluator_config.classes),
                source_evaluator=self.evaluator_config.source_evaluator,
            ),
        )
