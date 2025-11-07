from enum import Enum
from pydantic import BaseModel

class Severity(str, Enum):
    """Severity level for virtual resource operation results."""

    INFO = "info"
    SUCCESS = "success"
    ATTENTION = "attention"
    ERROR = "error"
    WARN = "warn"

class UiPathUpdateEvent(BaseModel):
    message: str
    severity: Severity
