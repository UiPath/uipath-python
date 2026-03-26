"""UiPath common exceptions."""

from enum import Enum


class ErrorCategory(str, Enum):
    """Categories of UiPath errors."""

    DEPLOYMENT = "Deployment"
    SYSTEM = "System"
    UNKNOWN = "Unknown"
    USER = "User"


class UiPathFaultedTriggerError(Exception):
    """UiPath resume trigger error."""

    category: ErrorCategory
    message: str
    detail: str

    def __init__(self, category: ErrorCategory, message: str, detail: str = ""):
        """Initialize the UiPathFaultedTriggerError."""
        self.category = category
        self.message = message
        self.detail = detail
        super().__init__(f"{message}: {detail}" if detail else message)


class UiPathPendingTriggerError(UiPathFaultedTriggerError):
    """Custom resume trigger error for pending triggers."""

    pass
