import json
import os
from functools import wraps
from importlib.metadata import version
from logging import INFO, WARNING, LogRecord, getLogger
from typing import Any, Callable, Dict, Mapping, Optional, Union

from opentelemetry.sdk._logs import LoggingHandler
from opentelemetry.util.types import AnyValue

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

# Try to import Application Insights client for custom events
# Note: applicationinsights is not typed, as it was deprecated in favor of the
# OpenTelemetry SDK. We still use it because it's the only way to send custom
# events to the Application Insights customEvents table.
try:
    from applicationinsights import (  # type: ignore[import-untyped]
        TelemetryClient as AppInsightsTelemetryClient,
    )

    _HAS_APPINSIGHTS = True
except ImportError:
    _HAS_APPINSIGHTS = False
    AppInsightsTelemetryClient = None


def _parse_connection_string(connection_string: str) -> Optional[str]:
    """Parse Azure Application Insights connection string to get instrumentation key.

    Args:
        connection_string: The full connection string from Azure.

    Returns:
        The instrumentation key if found, None otherwise.
    """
    try:
        parts = {}
        for part in connection_string.split(";"):
            if "=" in part:
                key, value = part.split("=", 1)
                parts[key] = value
        return parts.get("InstrumentationKey")
    except Exception:
        return None


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
    def _get_attributes(record: LogRecord) -> Mapping[str, AnyValue]:
        attributes = dict(LoggingHandler._get_attributes(record) or {})
        attributes[_APP_INSIGHTS_EVENT_MARKER_ATTRIBUTE] = True
        attributes[_CLOUD_TENANT_ID] = os.getenv(ENV_TENANT_ID, _UNKNOWN)
        attributes[_CLOUD_ORG_ID] = os.getenv(ENV_ORGANIZATION_ID, _UNKNOWN)
        attributes[_CLOUD_URL] = os.getenv(ENV_BASE_URL, _UNKNOWN)
        attributes[_APP_NAME] = "UiPath.Sdk"
        attributes[_SDK_VERSION] = version("uipath")
        try:
            # Lazy import to avoid circular dependency
            from .._cli._utils._common import get_claim_from_token

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

        return attributes


class _AppInsightsEventClient:
    """Application Insights SDK client for sending custom events.

    This uses the applicationinsights SDK to send events directly to the
    customEvents table in Application Insights.
    """

    _initialized = False
    _client: Optional[Any] = None

    @staticmethod
    def _initialize() -> None:
        """Initialize Application Insights client for custom events."""
        if _AppInsightsEventClient._initialized:
            return

        _AppInsightsEventClient._initialized = True

        if not _HAS_APPINSIGHTS:
            return

        connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
        if not connection_string:
            return

        try:
            instrumentation_key = _parse_connection_string(connection_string)
            if not instrumentation_key:
                return

            _AppInsightsEventClient._client = AppInsightsTelemetryClient(
                instrumentation_key
            )
        except Exception:
            # Silently fail - telemetry should never break the main application
            pass

    @staticmethod
    def track_event(
        name: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Track a custom event to Application Insights customEvents table.

        Args:
            name: Name of the event.
            properties: Properties for the event (converted to strings).
        """
        _AppInsightsEventClient._initialize()

        if not _AppInsightsEventClient._client:
            return

        try:
            safe_properties: Dict[str, str] = {}
            if properties:
                for key, value in properties.items():
                    if value is not None:
                        safe_properties[key] = str(value)

            _AppInsightsEventClient._client.track_event(
                name=name, properties=safe_properties, measurements={}
            )
            # Note: We don't flush after every event to avoid blocking.
            # Events will be sent in batches by the SDK.
        except Exception:
            # Telemetry should never break the main application
            pass

    @staticmethod
    def flush() -> None:
        """Flush any pending telemetry events."""
        if _AppInsightsEventClient._client:
            try:
                _AppInsightsEventClient._client.flush()
            except Exception:
                pass


class _TelemetryClient:
    """A class to handle telemetry using OpenTelemetry for method tracking."""

    _initialized = False

    @staticmethod
    def _is_enabled() -> bool:
        """Check if telemetry is enabled at runtime."""
        return os.getenv(ENV_TELEMETRY_ENABLED, "true").lower() == "true"

    @staticmethod
    def _initialize():
        """Initialize the OpenTelemetry-based telemetry client."""
        if _TelemetryClient._initialized or not _TelemetryClient._is_enabled():
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
        """Track function invocations using OpenTelemetry."""
        if not _TelemetryClient._is_enabled():
            return

        _TelemetryClient._initialize()

        _logger.info(f"Sdk.{name.capitalize()}", extra=attrs)

    @staticmethod
    def track_event(
        name: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Track a custom event to Application Insights customEvents table.

        This method sends a custom event using the Application Insights SDK,
        which ensures events appear in the customEvents table for monitoring
        and analytics. Telemetry failures are silently ignored to ensure the
        main application is never blocked.

        Args:
            name: Name of the event (e.g., "EvalSetRun.Start", "AgentRun.Complete").
            properties: Optional dictionary of properties to attach to the event.
                       Values will be converted to strings.

        Example:
            from uipath.telemetry import track_event

            track_event("MyFeature.Start", {"user_id": "123", "feature": "export"})
        """
        if not _TelemetryClient._is_enabled():
            return

        try:
            _AppInsightsEventClient.track_event(name, properties)
        except Exception:
            # Telemetry should never break the main application
            pass


def track_event(
    name: str,
    properties: Optional[Dict[str, Any]] = None,
) -> None:
    """Track a custom event.

    This function sends a custom event to Application Insights for monitoring
    and analytics. Telemetry failures are silently ignored to ensure the
    main application is never blocked.

    Args:
        name: Name of the event (e.g., "EvalSetRun.Start", "AgentRun.Complete").
        properties: Optional dictionary of properties to attach to the event.
                   Values will be converted to strings.

    Example:
        from uipath.telemetry import track_event

        track_event("MyFeature.Start", {"user_id": "123", "feature": "export"})
    """
    _TelemetryClient.track_event(name, properties)


def is_telemetry_enabled() -> bool:
    """Check if telemetry is enabled.

    Returns:
        True if telemetry is enabled, False otherwise.
    """
    return _TelemetryClient._is_enabled()


def flush_events() -> None:
    """Flush any pending telemetry events.

    Call this to ensure all tracked events are sent to Application Insights.
    This is useful at the end of a process or when you need to ensure
    events are sent immediately.
    """
    _AppInsightsEventClient.flush()


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
