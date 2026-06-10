"""Aggregator function ABC + the observation shape every function consumes."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from ._config import AggregatorConfig


@dataclass(frozen=True)
class Observation:
    """One per-datapoint expected/actual pair to aggregate over.

    Both fields are tolerant of None: a missing expected (no ground truth on
    that row) or missing actual (agent produced no output) is allowed; the
    function decides whether to skip or count it.
    """

    expected: str | None
    actual: str | None


class AggregatorFunction(ABC):
    """ABC for run-level aggregator functions.

    A function is purely (config, observations) -> float. Identity — which
    evaluator the observations came from — is the caller's bookkeeping.
    """

    name: str

    @abstractmethod
    def compute(
        self, config: AggregatorConfig, observations: list[Observation]
    ) -> float:
        """Compute the metric across all observations.

        Subclasses honor `config.classes` (or auto-infer when absent),
        `config.average` ("macro" / "micro" / "weighted"), and
        `config.positive_class` (binary mode).
        """
