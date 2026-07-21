"""Dataset-level classification evaluators: Precision, Recall, F-score, Confusion Matrix.

All variants share the same internal machinery — a k x k confusion matrix built
from each per-datapoint result's BaseEvaluatorJustification (expected, actual)
strings. The scalar variants (precision / recall / fscore) emit per-class
metrics plus micro/macro averages and pick the headline ``score`` per the
spec's ``averaging``; the ``confusion_matrix`` variant emits only the raw grid
with a 0.0 placeholder score.

The ``details`` payload is the platform wire contract: the Agents reducer
worker (python-dataset-eval-worker) calls this evaluator and ships
``details.model_dump(by_alias=True, exclude_none=True)`` verbatim to the C#
backend, where the frontend's zod schema
(frontend-sw/src/schemas/evaluations/evals.ts) validates it. Changing field
names or shapes here is a cross-repo breaking change.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from ..models.models import (
    EvaluationResult,
    EvaluationResultDto,
    NumericEvaluationResult,
)
from ._aggregator_specs import (
    ConfusionMatrixAggregatorSpec,
    FScoreAggregatorSpec,
)
from .base_dataset_evaluator import BaseDatasetEvaluator
from .base_evaluator import BaseEvaluatorJustification


class PerClassMetrics(BaseModel):
    """Per-class confusion counts plus all three scalar metrics for that class."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    tp: int
    tn: int
    fp: int
    fn: int
    support: int
    precision: float
    recall: float
    f_score: float


class AveragedMetrics(BaseModel):
    """Micro- or macro-averaged precision / recall / F-score triple."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    precision: float
    recall: float
    f_score: float


class ClassificationDetails(BaseModel):
    """Structured details payload emitted by every classification aggregator.

    The scalar metrics (precision / recall / fscore) populate every field;
    the ``confusion_matrix`` variant emits only the grid + counts, leaving
    ``averaging`` / ``f_value`` / ``per_class`` / ``macro`` / ``micro`` as
    None (excluded from the wire dump).
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    metric: str
    classes: list[str]
    confusion_matrix: list[list[int]] = Field(
        ...,
        description=(
            "k x k confusion matrix indexed as "
            "``confusion_matrix[predicted_idx][expected_idx]`` "
            "(rows are predicted classes, columns are expected). "
            "This is the transpose of sklearn's convention "
            "(``[true][predicted]``); UI / consumer code must use the "
            "orientation documented here."
        ),
    )
    n_total: int
    n_scored: int
    n_skipped: int
    averaging: str | None = None
    f_value: float | None = None
    per_class: dict[str, PerClassMetrics] | None = None
    macro: AveragedMetrics | None = None
    micro: AveragedMetrics | None = None


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
    ``classes`` are also skipped. Labels are normalized to lowercase for the
    lookup index so a classifier returning "Book" vs configured "book" still
    matches, but the user-supplied casing is preserved in the returned
    ``_ConfusionData.classes`` so downstream output (per_class keys, UI labels)
    shows what the user typed.
    """
    index_of = {c.lower(): i for i, c in enumerate(classes)}
    k = len(classes)
    matrix = [[0] * k for _ in range(k)]

    n_total = len(results)
    n_scored = 0
    n_skipped = 0

    for r in results:
        j = BaseEvaluatorJustification.try_from(r.details)
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
        classes=list(classes),
        matrix=matrix,
        n_total=n_total,
        n_scored=n_scored,
        n_skipped=n_skipped,
    )


def _f_beta(precision: float, recall: float, beta: float) -> float:
    b2 = beta * beta
    # denom == 0 iff precision == recall == 0 (both terms are non-negative and
    # beta > 0), which is exactly the zero-score case.
    denom = b2 * precision + recall
    if denom == 0:
        return 0.0
    return (1 + b2) * precision * recall / denom


class ClassificationDatasetEvaluator(BaseDatasetEvaluator):
    """One implementation for all classification aggregators.

    Scalar variants (precision / recall / fscore) compute the full per-class
    P/R/F report and pick the headline by the spec's ``averaging``; the
    ``confusion_matrix`` variant returns only the raw grid.
    """

    def evaluate(self, results: list[EvaluationResultDto]) -> EvaluationResult:
        """Compute the configured metric report and return the headline as score."""
        confusion = _build_confusion(results, self.classes)

        if isinstance(self.spec, ConfusionMatrixAggregatorSpec):
            # No scalar headline — emit the raw grid and let the UI render it.
            details = ClassificationDetails(
                metric=self.spec.type,
                classes=confusion.classes,
                confusion_matrix=confusion.matrix,
                n_total=confusion.n_total,
                n_scored=confusion.n_scored,
                n_skipped=confusion.n_skipped,
            )
            return NumericEvaluationResult(score=0.0, details=details)

        f_value = (
            self.spec.f_value if isinstance(self.spec, FScoreAggregatorSpec) else 1.0
        )
        k = len(confusion.classes)

        per_class: dict[str, PerClassMetrics] = {}
        precisions: list[float] = []
        recalls: list[float] = []
        f_scores: list[float] = []
        total_tp = total_fp = total_fn = 0

        for c, label in enumerate(confusion.classes):
            tp = confusion.matrix[c][c]
            row_sum = sum(confusion.matrix[c])  # predicted as `label`
            col_sum = sum(confusion.matrix[j][c] for j in range(k))  # true `label`
            fp = row_sum - tp
            fn = col_sum - tp
            tn = confusion.n_scored - tp - fp - fn

            precision = tp / row_sum if row_sum > 0 else 0.0
            recall = tp / col_sum if col_sum > 0 else 0.0
            f_score = _f_beta(precision, recall, f_value)

            per_class[label] = PerClassMetrics(
                tp=tp,
                tn=tn,
                fp=fp,
                fn=fn,
                support=tp + fn,
                precision=precision,
                recall=recall,
                f_score=f_score,
            )
            precisions.append(precision)
            recalls.append(recall)
            f_scores.append(f_score)
            total_tp += tp
            total_fp += fp
            total_fn += fn

        # AggregatorSpec classes come from the ExactMatch config which requires
        # a non-empty list, so k >= 1 always.
        macro = AveragedMetrics(
            precision=sum(precisions) / k,
            recall=sum(recalls) / k,
            f_score=sum(f_scores) / k,
        )
        micro_p = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
        micro_r = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
        micro = AveragedMetrics(
            precision=micro_p,
            recall=micro_r,
            f_score=_f_beta(micro_p, micro_r, f_value),
        )

        averaged = micro if self.spec.averaging == "micro" else macro
        headline = {
            "precision": averaged.precision,
            "recall": averaged.recall,
            "fscore": averaged.f_score,
        }[self.spec.type]

        details = ClassificationDetails(
            metric=self.spec.type,
            averaging=self.spec.averaging,
            f_value=f_value,
            classes=confusion.classes,
            confusion_matrix=confusion.matrix,
            per_class=per_class,
            macro=macro,
            micro=micro,
            n_total=confusion.n_total,
            n_scored=confusion.n_scored,
            n_skipped=confusion.n_skipped,
        )
        return NumericEvaluationResult(score=headline, details=details)
