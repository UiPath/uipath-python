"""UiPath Integration Service.

Connector activity execution and vendor HTTP requests through a connection.
"""

from ._integration_service import IntegrationService
from .execution_types import (
    ExecuteActivityResult,
    ExecuteFile,
    ExecuteHttpResult,
    ExecuteMethod,
    ExecutePage,
    ExecuteResult,
)

__all__ = [
    "IntegrationService",
    "ExecuteActivityResult",
    "ExecuteFile",
    "ExecuteHttpResult",
    "ExecuteMethod",
    "ExecutePage",
    "ExecuteResult",
]
