import json
import os
from functools import wraps
from importlib.metadata import version
from logging import INFO, WARNING, LogRecord, getLogger
from typing import Any, Callable, Dict, Optional, Union

from opentelemetry.sdk._logs import LoggingHandler
from opentelemetry.util.types import Attributes

from .._cli._utils._common import get_claim_from_token
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
    _CLOUD_USER_ID,
    _CODE_FILEPATH,
    _CODE_FUNCTION,
    _CODE_LINENO,
    _OTEL_RESOURCE_ATTRIBUTES,
    _PROJECT_KEY,
    _SDK_VERSION,
    _TELEMETRY_CONFIG_FILE,
    _UNKNOWN,
)

_logger = getLogger(__name__)
_logger.propagate = False


def _get_project_key() -> str:
    """Get project key from telemetry file if present.

    Returns:
        Project key string if available, otherwise empty string.
    """
    try:
        telemetry_file = os.path.join(".uipath", _TELEMETRY_CONFIG_FILE)
        if os.path.exists(telemetry_file):
            with open(telemetry_file, "r") as f:
                telemetry_data = json.load(f)
                project_id = telemetry_data.get(_PROJECT_KEY)
                if project_id:
                    return project_id
    except (json.JSONDecodeError, IOError, KeyError):
        pass

    return _UNKNOWN


class _AzureMonitorOpenTelemetryEventHandler(LoggingHandler):
    @staticmethod
    def _get_attributes(record: LogRecord) -> Attributes:  # type: ignore[override]
        attributes = dict(LoggingHandler._get_attributes(record) or {})
        attributes[_APP_INSIGHTS_EVENT_MARKER_ATTRIBUTE] = True
        attributes[_CLOUD_TENANT_ID] = os.getenv(ENV_TENANT_ID, _UNKNOWN)
        attributes[_CLOUD_ORG_ID] = os.getenv(ENV_ORGANIZATION_ID, _UNKNOWN)
        attributes[_CLOUD_URL] = os.getenv(ENV_BASE_URL, _UNKNOWN)
        attributes[_APP_NAME] = "UiPath.Sdk"
        attributes[_SDK_VERSION] = version("uipath")
        try:
            cloud_user_id = get_claim_from_token("sub")
        except Exception:
            cloud_user_id = _UNKNOWN
        attributes[_CLOUD_USER_ID] = cloud_user_id
        attributes[_PROJECT_KEY] = _get_project_key()

        if _CODE_FILEPATH in attributes:
            del attributes[_CODE_FILEPATH]
        if _CODE_FUNCTION in attributes:
            del attributes[_CODE_FUNCTION]
        if _CODE_LINENO in attributes:
            del attributes[_CODE_LINENO]

        return attributes  # type: ignore[return-value]


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
            os.environ["APPLICATIONINSIGHTS_STATSBEAT_DISABLED_ALL"] = "true"

            getLogger("azure").setLevel(WARNING)
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
