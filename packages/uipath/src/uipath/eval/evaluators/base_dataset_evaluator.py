"""Base abstractions for dataset-level evaluators.

A dataset-level evaluator runs once per evaluation set, after all per-datapoint
evaluators have produced their results. It consumes the per-datapoint
EvaluationResultDto values from one named source evaluator and emits a single
EvaluationResult that summarizes the dataset.

Concretely distinct from GenericBaseEvaluator: different evaluate() signature,
different lifecycle. Kept as a parallel hierarchy rather than a subclass so the
runtime cannot accidentally dispatch a dataset evaluator through the
per-datapoint loop.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..models.models import EvaluationResult, EvaluationResultDto
from ._aggregator_specs import AggregatorSpec


class BaseDatasetEvaluator(ABC):
    """Abstract base for dataset-level evaluators.

    Constructed from an :class:`AggregatorSpec`, the source evaluator's name,
    and the class vocabulary of the parent per-datapoint evaluator. Classes
    live on the evaluator config (not the spec) — every aggregator on the same
    evaluator operates on the same vocabulary.
    """

    spec: AggregatorSpec
    source_evaluator: str
    classes: list[str]

    def __init__(
        self, spec: AggregatorSpec, source_evaluator: str, classes: list[str]
    ) -> None:
        """Store the aggregator spec, source evaluator name, and shared classes."""
        self.spec = spec
        self.source_evaluator = source_evaluator
        self.classes = classes

    @abstractmethod
    def evaluate(self, results: list[EvaluationResultDto]) -> EvaluationResult:
        """Reduce per-datapoint results into a single run-level EvaluationResult."""
