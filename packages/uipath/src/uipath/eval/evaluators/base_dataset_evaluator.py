"""Base abstractions for dataset-level evaluators.

A dataset-level evaluator runs once per evaluation set, after all per-datapoint
evaluators have produced their results. It consumes the per-datapoint
EvaluationResultDto values from one named source evaluator and emits a single
EvaluationResult that summarizes the dataset.

Unlike the earlier pointer-style design, dataset evaluators no longer carry
their own JSON config or a ``source_evaluator`` field. They are constructed by
the factory directly from an :class:`AggregatorSpec` embedded in a per-datapoint
classification evaluator's config, together with the source evaluator's name
which is supplied externally by the runtime when walking those configs.

Concretely distinct from GenericBaseEvaluator: different evaluate() signature,
different lifecycle. Kept as a parallel hierarchy rather than a subclass so the
runtime cannot accidentally dispatch a dataset evaluator through the
per-datapoint loop.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from ..models.models import EvaluationResult, EvaluationResultDto
from ._aggregator_specs import AggregatorSpec

SpecT = TypeVar("SpecT", bound="AggregatorSpec")


class BaseDatasetEvaluator(ABC, Generic[SpecT]):
    """Abstract base for dataset-level evaluators.

    Constructed from an :class:`AggregatorSpec`, the class vocabulary of the
    parent per-datapoint evaluator, and the source evaluator's name. Classes
    live on the evaluator config (not the spec) — every aggregator on the same
    evaluator operates on the same vocabulary. The dataset evaluator's "name"
    used for result keying is derived from ``"{source_evaluator}.{spec.type}"``
    so two aggregators on the same source don't collide.
    """

    spec: SpecT
    source_evaluator: str
    classes: list[str]

    def __init__(self, spec: SpecT, source_evaluator: str, classes: list[str]) -> None:
        """Store the aggregator spec, source evaluator name, and shared classes."""
        self.spec = spec
        self.source_evaluator = source_evaluator
        self.classes = classes

    @property
    def name(self) -> str:
        """Stable key for this dataset evaluator's result in the output map."""
        return f"{self.source_evaluator}.{self.spec.type}"

    @abstractmethod
    def evaluate(self, results: list[EvaluationResultDto]) -> EvaluationResult:
        """Reduce per-datapoint results into a single run-level EvaluationResult."""
