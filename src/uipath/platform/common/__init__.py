"""UiPath Common Models.

This module contains common models used across multiple services.
"""

from ._api_client import ApiClient
from ._base_service import BaseService
from ._external_application_service import ExternalApplicationService
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
    "ApiClient",
    "BaseService",
    "ExternalApplicationService",
    "TokenData",
    "CreateTask",
    "CreateEscalation",
    "WaitEscalation",
    "InvokeProcess",
    "WaitTask",
    "WaitJob",
    "PagedResult",
]
