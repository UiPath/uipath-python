"""F-score aggregator (general F-beta).

`beta` defaults to 1.0 (F1). Set `beta=2.0` to weight recall higher
(F2), `beta=0.5` for precision-weighted (F0.5).
"""

from __future__ import annotations

from ._base import AggregatorFunction, Observation
from ._config import AggregatorConfig
from ._counts import (
    ClassCounts,
    class_counts,
    macro_average,
    resolve_classes,
    weighted_average,
)


def _f(beta: float, c: ClassCounts) -> float:
    """F-beta for one class. 0.0 when undefined (no TP and no relevant errors)."""
    b2 = beta * beta
    precision_denom = c.tp + c.fp
    recall_denom = c.tp + c.fn
    precision = c.tp / precision_denom if precision_denom > 0 else 0.0
    recall = c.tp / recall_denom if recall_denom > 0 else 0.0
    denom = b2 * precision + recall
    return (1 + b2) * precision * recall / denom if denom > 0 else 0.0


class FScoreAggregator(AggregatorFunction):
    """F-beta score over per-class precision/recall (beta=1 → F1)."""

    name = "fscore"

    def compute(
        self, config: AggregatorConfig, observations: list[Observation]
    ) -> float:
        """Compute the metric over the run-level observations."""
        classes = resolve_classes(config.classes, observations)
        if not classes:
            return 0.0

        if config.positive_class is not None:
            pos = config.positive_class
            tp = sum(1 for o in observations if o.expected == pos and o.actual == pos)
            fp = sum(1 for o in observations if o.expected != pos and o.actual == pos)
            fn = sum(1 for o in observations if o.expected == pos and o.actual != pos)
            return _f(config.beta, ClassCounts(tp=tp, fp=fp, fn=fn, support=tp + fn))

        counts = class_counts(classes, observations)
        per_class = [_f(config.beta, counts[c]) for c in classes]

        if config.average == "macro":
            return macro_average(per_class)
        if config.average == "micro":
            tp = sum(counts[c].tp for c in classes)
            fp = sum(counts[c].fp for c in classes)
            fn = sum(counts[c].fn for c in classes)
            return _f(config.beta, ClassCounts(tp=tp, fp=fp, fn=fn, support=tp + fn))
        weights = [counts[c].support for c in classes]
        return weighted_average(per_class, weights)
