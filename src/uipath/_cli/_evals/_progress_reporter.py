"""Backward compatibility - import from _reporting instead.

This module re-exports components from the _reporting package for
backward compatibility with existing code that imports from this location.

For new code, prefer importing directly from:
    from uipath._cli._evals._reporting import StudioWebProgressReporter
"""

from uipath._cli._evals._reporting import (
    CodedEvalReportingStrategy,
    EvalReportingStrategy,
    LegacyEvalReportingStrategy,
    StudioWebProgressReporter,
    gracefully_handle_errors,
)

__all__ = [
    "StudioWebProgressReporter",
    "EvalReportingStrategy",
    "LegacyEvalReportingStrategy",
    "CodedEvalReportingStrategy",
    "gracefully_handle_errors",
]
