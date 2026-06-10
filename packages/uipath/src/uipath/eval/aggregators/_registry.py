"""Function-name -> AggregatorFunction lookup."""

from __future__ import annotations

from ._base import AggregatorFunction
from .fscore import FScoreAggregator
from .precision import PrecisionAggregator
from .recall import RecallAggregator

default_registry: dict[str, AggregatorFunction] = {
    PrecisionAggregator.name: PrecisionAggregator(),
    RecallAggregator.name: RecallAggregator(),
    FScoreAggregator.name: FScoreAggregator(),
}


def get_function(name: str) -> AggregatorFunction:
    """Resolve an aggregator function by its `function` name in aggregate.json.

    Raises KeyError with the known names listed for actionable error messages.
    """
    try:
        return default_registry[name]
    except KeyError as exc:
        available = ", ".join(sorted(default_registry))
        raise KeyError(
            f"Unknown aggregator function '{name}'. Available: {available}"
        ) from exc
