"""Dataset-level classification evaluators: Precision, Recall, F-score.

All three share the same internal machinery — a k x k confusion matrix built
from each per-datapoint result's BaseEvaluatorJustification (expected, actual)
strings. They differ only in the final formula and (for F-score) the beta
parameter. The headline ``score`` is the micro or macro average per the
embedded :class:`AggregatorSpec`; ``details`` carries the full per-class
breakdown plus the confusion matrix.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from ..models.models import (
    EvaluationResult,
    EvaluationResultDto,
    NumericEvaluationResult,
)
from ._aggregator_specs import AggregatorSpec, FScoreAggregatorSpec
from .base_dataset_evaluator import BaseDatasetEvaluator
from .base_evaluator import BaseEvaluatorJustification


def _coerce_justification(details: object) -> BaseEvaluatorJustification | None:
    """Extract the BaseEvaluatorJustification from an EvaluationResultDto.details payload."""
    return BaseEvaluatorJustification.try_from(details)


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


@dataclass(slots=True)
class _ConfusionData:
    """Internal: confusion matrix and per-class counts derived from results."""

    classes: list[str]
    matrix: list[list[int]]
    n_total: int
    n_scored: int
    n_skipped: int


def _build_confusion(
    results: list[EvaluationResultDto],
    classes: list[str],
) -> _ConfusionData:
    """Build a confusion matrix from per-datapoint results.

    Results without a parseable justification are counted in ``n_skipped`` and
    omitted from the matrix. Pairs whose expected or actual label isn't in
    ``classes`` are also skipped. Labels are normalized to lowercase so a
    classifier returning "Book" vs configured "book" still matches.
    """
    canonical_classes = [c.lower() for c in classes]
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
        exp = j.expected.lower()
        act = j.actual.lower()
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


_METRIC_NAME = {"precision": "precision", "recall": "recall", "fscore": "f_score"}


class ClassificationDatasetEvaluator(BaseDatasetEvaluator[AggregatorSpec]):
    """One implementation for all three classification aggregators.

    Dispatches on ``self.spec.type`` to pick the per-class metric formula:
    precision, recall, or F-beta. The math (confusion-matrix build, per-class
    counts, micro/macro averaging) is identical across the three.
    """

    def evaluate(self, results: list[EvaluationResultDto]) -> EvaluationResult:
        """Compute the configured metric report and return the headline as score."""
        confusion = _build_confusion(results, self.spec.classes)
        beta_sq = (
            self.spec.f_value * self.spec.f_value
            if isinstance(self.spec, FScoreAggregatorSpec)
            else 0.0
        )
        metric_type = self.spec.type

        per_class: dict[str, PerClassMetrics] = {}
        total_tp = 0
        total_fp = 0
        total_fn = 0
        k = len(confusion.classes)

        for c, label in enumerate(confusion.classes):
            tp = confusion.matrix[c][c]
            fp = sum(confusion.matrix[c][j] for j in range(k)) - tp
            fn = sum(confusion.matrix[j][c] for j in range(k)) - tp
            tn = confusion.n_scored - tp - fp - fn
            total_tp += tp
            total_fp += fp
            total_fn += fn
            per_class[label] = PerClassMetrics(
                tp=tp,
                tn=tn,
                fp=fp,
                fn=fn,
                support=tp + fn,
                value=_metric(metric_type, tp, fp, fn, beta_sq),
            )

        micro = _metric(metric_type, total_tp, total_fp, total_fn, beta_sq)
        # AggregatorSpec.classes has min_length=1, so k >= 1 always.
        macro = sum(per_class[c].value for c in confusion.classes) / k

        details = ClassificationDetails(
            metric=_METRIC_NAME[metric_type],
            average=self.spec.averaging,
            classes=confusion.classes,
            confusion_matrix=confusion.matrix,
            per_class=per_class,
            micro=micro,
            macro=macro,
            n_total=confusion.n_total,
            n_scored=confusion.n_scored,
            n_skipped=confusion.n_skipped,
        )

        headline = micro if self.spec.averaging == "micro" else macro
        return NumericEvaluationResult(score=headline, details=details)


def _metric(metric_type: str, tp: int, fp: int, fn: int, beta_sq: float) -> float:
    """One formula switch covering precision / recall / F-beta."""
    if metric_type == "precision":
        return tp / (tp + fp) if (tp + fp) > 0 else 0.0
    if metric_type == "recall":
        return tp / (tp + fn) if (tp + fn) > 0 else 0.0
    p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    denom = beta_sq * p + r
    return (1 + beta_sq) * p * r / denom if denom > 0 else 0.0
