"""UiPath Common Models.

This module contains common models used across multiple services.
"""

from .auth import TokenData
from .interrupt_models import (
    CreateEscalation,
    CreateTask,
    InvokeProcess,
    WaitEscalation,
    WaitJob,
    WaitTask,
)
from .paging import PagedResult

__all__ = [
    "TokenData",
    "CreateTask",
    "CreateEscalation",
    "WaitEscalation",
    "InvokeProcess",
    "WaitTask",
    "WaitJob",
    "PagedResult",
]
