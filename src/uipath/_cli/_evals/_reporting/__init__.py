"""Evaluation progress reporting module.

This module provides components for reporting evaluation progress to StudioWeb,
supporting both legacy and coded evaluation formats through the Strategy Pattern.
"""

from uipath._cli._evals._reporting._reporter import StudioWebProgressReporter
from uipath._cli._evals._reporting._strategies import (
    CodedEvalReportingStrategy,
    EvalReportingStrategy,
    LegacyEvalReportingStrategy,
)
from uipath._cli._evals._reporting._utils import gracefully_handle_errors

__all__ = [
    "StudioWebProgressReporter",
    "EvalReportingStrategy",
    "LegacyEvalReportingStrategy",
    "CodedEvalReportingStrategy",
    "gracefully_handle_errors",
]
