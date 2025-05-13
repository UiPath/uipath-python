import os
from functools import wraps
from importlib.metadata import version
from logging import INFO, LogRecord, getLogger
from typing import Any, Callable, Dict, Optional, Union

from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry.sdk._logs import LoggingHandler
from opentelemetry.util.types import Attributes

from .._utils.constants import (
    ENV_BASE_URL,
    ENV_ORGANIZATION_ID,
    ENV_TELEMETRY_ENABLED,
    ENV_TENANT_ID,
)
from ._constants import (
    _APP_INSIGHTS_EVENT_MARKER_ATTRIBUTE,
    _APP_NAME,
    _CLOUD_ORG_ID,
    _CLOUD_TENANT_ID,
    _CLOUD_URL,
    _CODE_FILEPATH,
    _CODE_FUNCTION,
    _CODE_LINENO,
    _CONNECTION_STRING,
    _OTEL_RESOURCE_ATTRIBUTES,
    _SDK_VERSION,
    _UNKNOWN,
)

_logger = getLogger(__name__)
_logger.propagate = False


class _AzureMonitorOpenTelemetryEventHandler(LoggingHandler):
    @staticmethod
    def _get_attributes(record: LogRecord) -> Attributes:
        attributes = dict(LoggingHandler._get_attributes(record) or {})
        attributes[_APP_INSIGHTS_EVENT_MARKER_ATTRIBUTE] = True
        attributes[_CLOUD_TENANT_ID] = os.getenv(ENV_TENANT_ID, _UNKNOWN)
        attributes[_CLOUD_ORG_ID] = os.getenv(ENV_ORGANIZATION_ID, _UNKNOWN)
        attributes[_CLOUD_URL] = os.getenv(ENV_BASE_URL, _UNKNOWN)
        attributes[_APP_NAME] = "UiPath.Sdk"
        attributes[_SDK_VERSION] = version("uipath")

        if _CODE_FILEPATH in attributes:
            del attributes[_CODE_FILEPATH]
        if _CODE_FUNCTION in attributes:
            del attributes[_CODE_FUNCTION]
        if _CODE_LINENO in attributes:
            del attributes[_CODE_LINENO]

        return attributes


class _TelemetryClient:
    """A class to handle telemetry."""

    _initialized = False
    _enabled = os.getenv(ENV_TELEMETRY_ENABLED, "true").lower() == "true"

    @staticmethod
    def _initialize():
        """Initialize the telemetry client."""
        if _TelemetryClient._initialized or not _TelemetryClient._enabled:
            return

        try:
            os.environ[_OTEL_RESOURCE_ATTRIBUTES] = (
                "service.name=uipath-sdk,service.instance.id=" + version("uipath")
            )
            os.environ["OTEL_TRACES_EXPORTER"] = "none"

            configure_azure_monitor(
                connection_string=_CONNECTION_STRING,
                disable_offline_storage=True,
            )

            _logger.addHandler(_AzureMonitorOpenTelemetryEventHandler())
            _logger.setLevel(INFO)

            _TelemetryClient._initialized = True
        except Exception:
            pass

    @staticmethod
    def _track_method(name: str, attrs: Optional[Dict[str, Any]] = None):
        """Track function invocations."""
        if not _TelemetryClient._enabled:
            return

        _TelemetryClient._initialize()

        _logger.info(f"Sdk.{name.capitalize()}", extra=attrs)


def track(
    name_or_func: Optional[Union[str, Callable[..., Any]]] = None,
    *,
    when: Optional[Union[bool, Callable[..., bool]]] = True,
    extra: Optional[Dict[str, Any]] = None,
):
    """Decorator that will trace function invocations.

    Args:
        name_or_func: The name of the event to track or the function itself.
        extra: Extra attributes to add to the telemetry event.
    """

    def decorator(func: Callable[..., Any]):
        @wraps(func)
        def wrapper(*args, **kwargs):
            event_name = (
                name_or_func if isinstance(name_or_func, str) else func.__name__
            )

            should_track = when(*args, **kwargs) if callable(when) else when

            if should_track:
                _TelemetryClient._track_method(event_name, extra)

            return func(*args, **kwargs)

        return wrapper

    if callable(name_or_func):
        return decorator(name_or_func)

    return decorator
