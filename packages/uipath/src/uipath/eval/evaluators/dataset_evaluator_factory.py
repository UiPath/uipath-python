"""Factory that instantiates dataset-level evaluators from aggregator specs.

Dataset evaluators are built from a self-contained :class:`AggregatorSpec`
embedded in a per-datapoint classification evaluator's config, plus the source
evaluator's name (supplied by the runtime when walking those configs). All
three aggregator types share a single :class:`ClassificationDatasetEvaluator`
implementation that dispatches on ``spec.type`` internally.
"""

from __future__ import annotations

from ._aggregator_specs import AggregatorSpec
from .classification_dataset_evaluators import ClassificationDatasetEvaluator


def build_dataset_evaluator(
    spec: AggregatorSpec,
    source_evaluator: str,
    classes: list[str],
) -> ClassificationDatasetEvaluator:
    """Build a dataset evaluator instance from an aggregator spec.

    Args:
        spec: A validated :class:`AggregatorSpec` (precision / recall / fscore).
        source_evaluator: Name of the per-datapoint evaluator whose results
            this aggregator consumes.
        classes: The class vocabulary from the parent evaluator's config. Shared
            across all aggregators attached to that evaluator — a spec no longer
            carries classes of its own.
    """
    return ClassificationDatasetEvaluator(spec, source_evaluator, classes)
