"""Run-level aggregator functions for `uipath eval --aggregate-config`.

An aggregator function is a pure function from a list of
`(expected_class, predicted_class)` observations + per-aggregator config
to a single number. Functions are registered by name and resolved at
post-pass time from the `aggregate.json` file the user passes to the CLI.

Today's registry: `precision`, `recall`, `fscore`. All three share the
same observation extraction (multi-class with macro/micro/weighted
averaging) and a common per-aggregator config: `classes` (optional, auto-
inferred from observations when omitted), `average`, `positiveClass`,
and `beta` (fscore only).
"""

from ._base import AggregatorFunction, Observation
from ._config import AggregateConfig, AggregatorConfig
from ._postpass import apply_to_output_file, compute_aggregations
from ._registry import default_registry, get_function
from .fscore import FScoreAggregator
from .precision import PrecisionAggregator
from .recall import RecallAggregator

__all__ = [
    "AggregateConfig",
    "AggregatorConfig",
    "AggregatorFunction",
    "FScoreAggregator",
    "Observation",
    "PrecisionAggregator",
    "RecallAggregator",
    "apply_to_output_file",
    "compute_aggregations",
    "default_registry",
    "get_function",
]
