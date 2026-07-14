"""Self-contained port of the IXP Measure scoring math from ixp-platform.

Pure Python (stdlib + dateutil): Hungarian row matching, typed value
equality, confusion bucketing, micro-averaged precision/recall/F1,
variability bands, quality bands. Parity is pinned by ixp-platform's own
golden fixtures (see tests/evaluators/ixp/).
"""

from .ixp import (
    IxpSummaryMetrics,
    RawIxpMetrics,
    RawIxpMetricsFromMoon,
    raw_ixp_metrics_to_summary,
)
from .moon import match_captures, moon_extractions_are_equal
from .ranged_value import RangedValue

__all__ = (
    "IxpSummaryMetrics",
    "RangedValue",
    "RawIxpMetrics",
    "RawIxpMetricsFromMoon",
    "match_captures",
    "moon_extractions_are_equal",
    "raw_ixp_metrics_to_summary",
)
