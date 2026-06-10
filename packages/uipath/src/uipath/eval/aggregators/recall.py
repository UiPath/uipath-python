"""Recall aggregator."""

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


def _recall(c: ClassCounts) -> float:
    denom = c.tp + c.fn
    return c.tp / denom if denom > 0 else 0.0


class RecallAggregator(AggregatorFunction):
    """Per-class recall (TP / (TP + FN)) with macro/micro/weighted averaging."""

    name = "recall"

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
            fn = sum(1 for o in observations if o.expected == pos and o.actual != pos)
            denom = tp + fn
            return tp / denom if denom > 0 else 0.0

        counts = class_counts(classes, observations)
        per_class = [_recall(counts[c]) for c in classes]

        if config.average == "macro":
            return macro_average(per_class)
        if config.average == "micro":
            tp = sum(counts[c].tp for c in classes)
            fn = sum(counts[c].fn for c in classes)
            denom = tp + fn
            return tp / denom if denom > 0 else 0.0
        weights = [counts[c].support for c in classes]
        return weighted_average(per_class, weights)
