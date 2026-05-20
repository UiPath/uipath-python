"""Factory that instantiates dataset-level evaluators from configuration."""

from __future__ import annotations

from typing import Any

from ..models.models import EvaluatorType
from .base_dataset_evaluator import BaseDatasetEvaluator
from .classification_dataset_evaluators import (
    FScoreDatasetEvaluator,
    FScoreDatasetEvaluatorConfig,
    PrecisionDatasetEvaluator,
    PrecisionDatasetEvaluatorConfig,
    RecallDatasetEvaluator,
    RecallDatasetEvaluatorConfig,
)

_EVALUATOR_REGISTRY: dict[str, type[BaseDatasetEvaluator[Any]]] = {
    EvaluatorType.DATASET_PRECISION.value: PrecisionDatasetEvaluator,
    EvaluatorType.DATASET_RECALL.value: RecallDatasetEvaluator,
    EvaluatorType.DATASET_F_SCORE.value: FScoreDatasetEvaluator,
}

_CONFIG_REGISTRY: dict[str, type[Any]] = {
    EvaluatorType.DATASET_PRECISION.value: PrecisionDatasetEvaluatorConfig,
    EvaluatorType.DATASET_RECALL.value: RecallDatasetEvaluatorConfig,
    EvaluatorType.DATASET_F_SCORE.value: FScoreDatasetEvaluatorConfig,
}


def build_dataset_evaluator(
    config_data: dict[str, Any],
) -> BaseDatasetEvaluator[Any]:
    """Build a dataset evaluator instance from a parsed JSON config dict.

    Raises:
        ValueError: If ``type`` is missing or unknown.
    """
    evaluator_type = config_data.get("type")
    if not evaluator_type:
        raise ValueError("Dataset evaluator config is missing required field 'type'")

    config_cls = _CONFIG_REGISTRY.get(evaluator_type)
    evaluator_cls = _EVALUATOR_REGISTRY.get(evaluator_type)
    if config_cls is None or evaluator_cls is None:
        known = sorted(_EVALUATOR_REGISTRY.keys())
        raise ValueError(
            f"Unknown dataset evaluator type '{evaluator_type}'. Known types: {known}"
        )

    config = config_cls.model_validate(config_data)
    return evaluator_cls(config)
