"""UiPath core exceptions module.

This module exposes common UiPath exceptions.
"""

from .errors import (
    ErrorCategory,
    UiPathFaultedTriggerError,
    UiPathPendingTriggerError,
)

__all__ = ["UiPathFaultedTriggerError", "UiPathPendingTriggerError", "ErrorCategory"]
