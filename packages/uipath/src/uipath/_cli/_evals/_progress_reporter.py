"""Progress reporter for sending evaluation updates to StudioWeb.

This module is a compatibility shim: the implementation moved to the
``_reporting`` package, where the legacy/coded API differences are handled
by strategy classes.
"""

from ._reporting import (
    EvaluationStatus,
    StudioWebAgentSnapshot,
    StudioWebProgressItem,
    StudioWebProgressReporter,
    gracefully_handle_errors,
)

__all__ = [
    "EvaluationStatus",
    "StudioWebAgentSnapshot",
    "StudioWebProgressItem",
    "StudioWebProgressReporter",
    "gracefully_handle_errors",
]
