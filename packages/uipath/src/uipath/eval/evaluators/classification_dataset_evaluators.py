"""Dataset-level classification evaluators: Precision, Recall, F-score.

All three share the same internal machinery — a k x k confusion matrix built
from each per-datapoint result's BaseEvaluatorJustification (expected, actual)
strings. They differ only in the final formula and (for F-score) the beta
parameter. The headline ``score`` is the micro or macro average per config;
``details`` carries the full per-class breakdown plus the confusion matrix.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from ..models.models import (
    EvaluationResult,
    EvaluationResultDto,
    EvaluatorType,
    NumericEvaluationResult,
)
from .base_dataset_evaluator import BaseDatasetEvaluator, BaseDatasetEvaluatorConfig
from .base_evaluator import BaseEvaluatorJustification


def _coerce_justification(details: object) -> tuple[str, str] | None:
    """Extract (expected, actual) from an EvaluationResultDto.details payload."""
    if isinstance(details, BaseEvaluatorJustification):
        return details.expected, details.actual
    if isinstance(details, dict):
        try:
            j = BaseEvaluatorJustification.model_validate(details)
        except Exception:
            return None
        return j.expected, j.actual
    return None


class PerClassMetrics(BaseModel):
    """Per-class confusion counts plus the metric the evaluator computed."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    tp: int
    tn: int
    fp: int
    fn: int
    support: int
    value: float


class ClassificationDetails(BaseModel):
    """Structured details payload emitted by every classification evaluator."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    metric: str
    average: str
    classes: list[str]
    confusion_matrix: list[list[int]]
    per_class: dict[str, PerClassMetrics]
    micro: float
    macro: float
    n_total: int
    n_scored: int
    n_skipped: int


class _ConfusionData:
    """Internal: confusion matrix and per-class counts derived from results."""

    __slots__ = ("classes", "matrix", "n_total", "n_scored", "n_skipped")

    def __init__(
        self,
        classes: list[str],
        matrix: list[list[int]],
        n_total: int,
        n_scored: int,
        n_skipped: int,
    ) -> None:
        self.classes = classes
        self.matrix = matrix
        self.n_total = n_total
        self.n_scored = n_scored
        self.n_skipped = n_skipped

    def counts_for(self, class_index: int) -> tuple[int, int, int, int]:
        """Return (tp, fp, fn, tn) for a class index."""
        k = len(self.classes)
        tp = self.matrix[class_index][class_index]
        fp = sum(self.matrix[class_index][j] for j in range(k)) - tp
        fn = sum(self.matrix[j][class_index] for j in range(k)) - tp
        tn = self.n_scored - tp - fp - fn
        return tp, fp, fn, tn


def _build_confusion(
    results: list[EvaluationResultDto],
    classes: list[str],
    case_sensitive: bool,
) -> _ConfusionData:
    """Build a confusion matrix from per-datapoint results.

    Results without a parseable justification are counted in ``n_skipped`` and
    omitted from the matrix. Pairs whose expected or actual label isn't in
    ``classes`` are also skipped.
    """

    def norm(label: str) -> str:
        return label if case_sensitive else label.lower()

    canonical_classes = [norm(c) for c in classes]
    index_of = {c: i for i, c in enumerate(canonical_classes)}
    k = len(canonical_classes)
    matrix = [[0] * k for _ in range(k)]

    n_total = len(results)
    n_scored = 0
    n_skipped = 0

    for r in results:
        j = _coerce_justification(r.details)
        if j is None:
            n_skipped += 1
            continue
        exp = norm(j[0])
        act = norm(j[1])
        if exp not in index_of or act not in index_of:
            n_skipped += 1
            continue
        matrix[index_of[act]][index_of[exp]] += 1
        n_scored += 1

    return _ConfusionData(
        classes=canonical_classes,
        matrix=matrix,
        n_total=n_total,
        n_scored=n_scored,
        n_skipped=n_skipped,
    )


def _precision_of(tp: int, fp: int, _fn: int, _tn: int) -> float:
    return tp / (tp + fp) if (tp + fp) > 0 else 0.0


def _recall_of(tp: int, _fp: int, fn: int, _tn: int) -> float:
    return tp / (tp + fn) if (tp + fn) > 0 else 0.0


def _f_score_of(beta: float):
    beta_sq = beta * beta

    def compute(tp: int, fp: int, fn: int, _tn: int) -> float:
        p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        denom = beta_sq * p + r
        return (1 + beta_sq) * p * r / denom if denom > 0 else 0.0

    return compute


def _build_details(
    confusion: _ConfusionData,
    metric_name: str,
    average: str,
    per_class_fn,
) -> tuple[ClassificationDetails, float]:
    """Compute per-class values, micro, macro, and pick the headline.

    Returns (details, headline_score). ``headline_score`` is the micro or macro
    average per the evaluator's ``average`` setting.
    """
    per_class: dict[str, PerClassMetrics] = {}
    total_tp = 0
    total_fp = 0
    total_fn = 0

    for c, label in enumerate(confusion.classes):
        tp, fp, fn, tn = confusion.counts_for(c)
        total_tp += tp
        total_fp += fp
        total_fn += fn
        per_class[label] = PerClassMetrics(
            tp=tp,
            tn=tn,
            fp=fp,
            fn=fn,
            support=tp + fn,
            value=per_class_fn(tp, fp, fn, tn),
        )

    micro = per_class_fn(total_tp, total_fp, total_fn, 0)

    k = len(confusion.classes)
    macro = sum(per_class[c].value for c in confusion.classes) / k if k > 0 else 0.0

    details = ClassificationDetails(
        metric=metric_name,
        average=average,
        classes=confusion.classes,
        confusion_matrix=confusion.matrix,
        per_class=per_class,
        micro=micro,
        macro=macro,
        n_total=confusion.n_total,
        n_scored=confusion.n_scored,
        n_skipped=confusion.n_skipped,
    )

    headline = micro if average == "micro" else macro
    return details, headline


# ─── configs ──────────────────────────────────────────────────────────────────


class _BaseClassificationConfig(BaseDatasetEvaluatorConfig):
    """Shared config for the three classification evaluators."""

    classes: list[str] = Field(
        ...,
        min_length=1,
        description="Class labels expected in the upstream evaluator's justifications.",
    )
    average: Literal["micro", "macro"] = "macro"
    case_sensitive: bool = False


class PrecisionDatasetEvaluatorConfig(_BaseClassificationConfig):
    """Configuration for the dataset-level precision evaluator."""

    type: str = EvaluatorType.DATASET_PRECISION.value


class RecallDatasetEvaluatorConfig(_BaseClassificationConfig):
    """Configuration for the dataset-level recall evaluator."""

    type: str = EvaluatorType.DATASET_RECALL.value


class FScoreDatasetEvaluatorConfig(_BaseClassificationConfig):
    """Configuration for the dataset-level F-score evaluator."""

    type: str = EvaluatorType.DATASET_F_SCORE.value
    f_value: float = Field(default=1.0, gt=0, description="Beta value for F_beta.")


# ─── evaluators ───────────────────────────────────────────────────────────────


class PrecisionDatasetEvaluator(BaseDatasetEvaluator[PrecisionDatasetEvaluatorConfig]):
    """Dataset-level precision evaluator (multiclass, micro or macro averaged)."""

    @classmethod
    def get_evaluator_id(cls) -> str:
        """Identifier matching the type discriminator on configs."""
        return EvaluatorType.DATASET_PRECISION.value

    def evaluate(self, results: list[EvaluationResultDto]) -> EvaluationResult:
        """Compute the precision report and return the headline as score."""
        confusion = _build_confusion(
            results, self.config.classes, self.config.case_sensitive
        )
        details, headline = _build_details(
            confusion, "precision", self.config.average, _precision_of
        )
        return NumericEvaluationResult(score=headline, details=details)


class RecallDatasetEvaluator(BaseDatasetEvaluator[RecallDatasetEvaluatorConfig]):
    """Dataset-level recall evaluator (multiclass, micro or macro averaged)."""

    @classmethod
    def get_evaluator_id(cls) -> str:
        """Identifier matching the type discriminator on configs."""
        return EvaluatorType.DATASET_RECALL.value

    def evaluate(self, results: list[EvaluationResultDto]) -> EvaluationResult:
        """Compute the recall report and return the headline as score."""
        confusion = _build_confusion(
            results, self.config.classes, self.config.case_sensitive
        )
        details, headline = _build_details(
            confusion, "recall", self.config.average, _recall_of
        )
        return NumericEvaluationResult(score=headline, details=details)


class FScoreDatasetEvaluator(BaseDatasetEvaluator[FScoreDatasetEvaluatorConfig]):
    """Dataset-level F-beta evaluator (multiclass, micro or macro averaged)."""

    @classmethod
    def get_evaluator_id(cls) -> str:
        """Identifier matching the type discriminator on configs."""
        return EvaluatorType.DATASET_F_SCORE.value

    def evaluate(self, results: list[EvaluationResultDto]) -> EvaluationResult:
        """Compute the F-beta report and return the headline as score."""
        confusion = _build_confusion(
            results, self.config.classes, self.config.case_sensitive
        )
        details, headline = _build_details(
            confusion,
            "f_score",
            self.config.average,
            _f_score_of(self.config.f_value),
        )
        return NumericEvaluationResult(score=headline, details=details)
