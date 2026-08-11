"""Factory that instantiates dataset-level evaluators from aggregator specs.

Dataset evaluators are built from a self-contained :class:`AggregatorSpec`
embedded in a per-datapoint classification evaluator's config, plus the source
evaluator's name (supplied by the runtime when walking those configs). All
three aggregator types share a single :class:`ClassificationDatasetEvaluator`
implementation that dispatches on ``spec.type`` internally.
"""

from __future__ import annotations

from typing import Sequence

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


def unique_aggregator_specs(specs: Sequence[AggregatorSpec]) -> list[AggregatorSpec]:
    """Drop exact-duplicate specs (same type and parameters), preserving order."""
    seen: set[str] = set()
    unique: list[AggregatorSpec] = []
    for spec in specs:
        dumped = spec.model_dump_json()
        if dumped not in seen:
            seen.add(dumped)
            unique.append(spec)
    return unique


def dataset_result_key(
    source_evaluator: str, spec: AggregatorSpec, duplicate_type: bool
) -> str:
    """Result-map key shared by `uipath eval` and the platform worker.

    ``{source}::{type}``, extended with ``.{averaging}`` (and ``.fb{f_value}``
    for fscore) when the same type appears more than once on one source.
    Callers must dedupe via :func:`unique_aggregator_specs` first — after that,
    duplicate types always differ in averaging or f_value.
    """
    key = f"{source_evaluator}::{spec.type}"
    averaging = getattr(spec, "averaging", None)
    if not duplicate_type or averaging is None:
        return key
    f_value = getattr(spec, "f_value", None)
    if f_value is not None:
        return f"{key}.{averaging}.fb{f_value}"
    return f"{key}.{averaging}"
