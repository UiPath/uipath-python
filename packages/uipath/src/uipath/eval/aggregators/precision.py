"""Precision aggregator."""

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


def _precision(c: ClassCounts) -> float:
    denom = c.tp + c.fp
    return c.tp / denom if denom > 0 else 0.0


class PrecisionAggregator(AggregatorFunction):
    """Per-class precision (TP / (TP + FP)) with macro/micro/weighted averaging."""

    name = "precision"

    def compute(
        self, config: AggregatorConfig, observations: list[Observation]
    ) -> float:
        """Compute the metric over the run-level observations."""
        classes = resolve_classes(config.classes, observations)
        if not classes:
            return 0.0

        # Binary mode: single positive class. Treat everything else as "other".
        if config.positive_class is not None:
            pos = config.positive_class
            tp = sum(1 for o in observations if o.expected == pos and o.actual == pos)
            fp = sum(1 for o in observations if o.expected != pos and o.actual == pos)
            denom = tp + fp
            return tp / denom if denom > 0 else 0.0

        counts = class_counts(classes, observations)
        per_class = [_precision(counts[c]) for c in classes]

        if config.average == "macro":
            return macro_average(per_class)
        if config.average == "micro":
            tp = sum(counts[c].tp for c in classes)
            fp = sum(counts[c].fp for c in classes)
            denom = tp + fp
            return tp / denom if denom > 0 else 0.0
        # weighted
        weights = [counts[c].support for c in classes]
        return weighted_average(per_class, weights)
