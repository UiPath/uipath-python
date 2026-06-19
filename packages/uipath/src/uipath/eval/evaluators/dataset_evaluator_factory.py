"""Factory that instantiates dataset-level evaluators from aggregator specs.

Dataset evaluators are now built from a self-contained :class:`AggregatorSpec`
embedded in a per-datapoint classification evaluator's config, plus the source
evaluator's name (supplied by the runtime when walking those configs). The
factory inspects the spec's ``type`` discriminator and returns the matching
evaluator instance.
"""

from __future__ import annotations

from typing import Any

from ._aggregator_specs import (
    AggregatorSpec,
    FScoreAggregatorSpec,
    PrecisionAggregatorSpec,
    RecallAggregatorSpec,
)
from .base_dataset_evaluator import BaseDatasetEvaluator
from .classification_dataset_evaluators import (
    FScoreDatasetEvaluator,
    PrecisionDatasetEvaluator,
    RecallDatasetEvaluator,
)

_EVALUATOR_REGISTRY: dict[str, type[BaseDatasetEvaluator[Any]]] = {
    "precision": PrecisionDatasetEvaluator,
    "recall": RecallDatasetEvaluator,
    "fscore": FScoreDatasetEvaluator,
}


def build_dataset_evaluator(
    spec: AggregatorSpec,
    source_evaluator: str,
) -> BaseDatasetEvaluator[Any]:
    """Build a dataset evaluator instance from an aggregator spec.

    Args:
        spec: A validated :class:`AggregatorSpec` (precision / recall / fscore).
        source_evaluator: Name of the per-datapoint evaluator whose results
            this aggregator consumes.

    Raises:
        ValueError: If ``spec.type`` doesn't match any known aggregator.
    """
    evaluator_cls = _EVALUATOR_REGISTRY.get(spec.type)
    if evaluator_cls is None:
        known = sorted(_EVALUATOR_REGISTRY.keys())
        raise ValueError(f"Unknown aggregator type '{spec.type}'. Known types: {known}")
    return evaluator_cls(spec, source_evaluator)


__all__ = [
    "AggregatorSpec",
    "PrecisionAggregatorSpec",
    "RecallAggregatorSpec",
    "FScoreAggregatorSpec",
    "build_dataset_evaluator",
]
