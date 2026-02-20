"""Re-export from uipath.platform for backward compatibility."""

from uipath.platform.common._endpoints_manager import EndpointManager  # noqa: D104

__all__ = [
    "EndpointManager",
]
