"""Base abstractions for dataset-level evaluators.

A dataset-level evaluator runs once per evaluation set, after all per-datapoint
evaluators have produced their results. It consumes the per-datapoint
EvaluationResultDto values from one named source evaluator and emits a single
EvaluationResult that summarizes the dataset.

Concretely distinct from GenericBaseEvaluator: different evaluate() signature,
different lifecycle. Kept as a parallel hierarchy rather than a subclass so
the runtime cannot accidentally dispatch a dataset evaluator through the
per-datapoint loop.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from ..models.models import EvaluationResult, EvaluationResultDto


class BaseDatasetEvaluatorConfig(BaseModel):
    """Configuration shared by all dataset-level evaluators."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    id: str
    name: str
    type: str
    source_evaluator: str = Field(
        ...,
        description=(
            "Name of the per-datapoint evaluator whose EvaluationResultDto values "
            "this dataset evaluator consumes."
        ),
    )


ConfigT = TypeVar("ConfigT", bound=BaseDatasetEvaluatorConfig)


class BaseDatasetEvaluator(ABC, Generic[ConfigT]):
    """Abstract base for dataset-level evaluators.

    Subclasses implement ``evaluate`` over the per-datapoint EvaluationResultDto
    values produced by ``config.source_evaluator``.
    """

    config: ConfigT

    def __init__(self, config: ConfigT) -> None:
        """Store the evaluator's configuration."""
        self.config = config

    @property
    def name(self) -> str:
        """Logical name of this evaluator instance (used as result-dict key)."""
        return self.config.name

    @property
    def source_evaluator(self) -> str:
        """Name of the upstream evaluator whose results this one consumes."""
        return self.config.source_evaluator

    @classmethod
    @abstractmethod
    def get_evaluator_id(cls) -> str:
        """Stable identifier matching the ``type`` discriminator on configs."""

    @abstractmethod
    def evaluate(self, results: list[EvaluationResultDto]) -> EvaluationResult:
        """Reduce per-datapoint results into a single run-level EvaluationResult."""
