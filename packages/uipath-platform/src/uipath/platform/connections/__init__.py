"""UiPath Connections Models.

This module contains models related to UiPath Connections service.
"""

from ._connections_service import ConnectionsService
from .connections import (
    ActivityMetadata,
    ActivityParameterLocationInfo,
    Connection,
    ConnectionMetadata,
    ConnectionToken,
    ConnectionTokenType,
    EventArguments,
)

__all__ = [
    "ConnectionsService",
    "ActivityMetadata",
    "ActivityParameterLocationInfo",
    "Connection",
    "ConnectionMetadata",
    "ConnectionToken",
    "ConnectionTokenType",
    "EventArguments",
]
