import atexit
import json
import os
from functools import wraps
from importlib.metadata import version
from logging import INFO, WARNING, LogRecord, getLogger
from typing import Any, Callable, ClassVar, Dict, Mapping, Optional, Union

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
    _CONNECTION_STRING,
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
    from applicationinsights.channel import (  # type: ignore[import-untyped]
        SynchronousQueue,
        SynchronousSender,
        TelemetryChannel,
    )

    _HAS_APPINSIGHTS = True
except ImportError:
    _HAS_APPINSIGHTS = False
    AppInsightsTelemetryClient = None
    SynchronousSender = None
    SynchronousQueue = None
    TelemetryChannel = None


def _parse_connection_string(
    connection_string: str,
) -> Optional[Dict[str, str]]:
    """Parse Azure Application Insights connection string.

    Args:
        connection_string: The full connection string from Azure.

    Returns:
        Dict with 'InstrumentationKey' and optionally 'IngestionEndpoint',
        or None if InstrumentationKey is not found.
    """
    try:
        parts: Dict[str, str] = {}
        for part in connection_string.split(";"):
            if "=" in part:
                key, value = part.split("=", 1)
                parts[key] = value
        ikey = parts.get("InstrumentationKey")
        if not ikey:
            return None
        result: Dict[str, str] = {"InstrumentationKey": ikey}
        ingestion = parts.get("IngestionEndpoint")
        if ingestion:
            result["IngestionEndpoint"] = ingestion
        return result
    except Exception:
        return None


_logger = getLogger(__name__)
_logger.propagate = False


def _get_connection_string() -> str | None:
    """Get the Application Insights connection string.

    Checks the TELEMETRY_CONNECTION_STRING env var first, then falls back
    to the _CONNECTION_STRING constant.
    """
    env_value = os.getenv("TELEMETRY_CONNECTION_STRING")
    if env_value:
        return env_value
    if _CONNECTION_STRING and _CONNECTION_STRING != "$CONNECTION_STRING":
        return _CONNECTION_STRING
    return None


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


class _DiagnosticSender(SynchronousSender):
    """SynchronousSender that logs HTTP failures the base SDK silently discards."""

    def send(self, data_to_send: Any) -> None:
        """Send telemetry data with diagnostic logging.

        The base SDK silently discards HTTP 400 responses and swallows all
        other network errors. This override adds WARNING-level logs so
        silent data loss becomes visible in logs.
        """
        import json as _json

        try:
            import urllib.request as HTTPClient
            from urllib.error import HTTPError
        except ImportError:
            super().send(data_to_send)
            return

        request_payload = _json.dumps([a.write() for a in data_to_send])
        request = HTTPClient.Request(
            self._service_endpoint_uri,
            bytearray(request_payload, "utf-8"),
            {
                "Accept": "application/json",
                "Content-Type": "application/json; charset=utf-8",
            },
        )
        try:
            response = HTTPClient.urlopen(request, timeout=self._timeout)
            status_code = response.getcode()
            if 200 <= status_code < 300:
                return
        except HTTPError as e:
            if e.getcode() == 400:
                _logger.warning(
                    "AppInsights send: HTTP 400 — payload rejected (%d items discarded)",
                    len(data_to_send),
                )
                return
            _logger.warning(
                "AppInsights send: HTTP %d (%d items re-queued)",
                e.getcode(),
                len(data_to_send),
            )
        except Exception as e:
            _logger.warning("AppInsights send: %s (%s)", type(e).__name__, e)

        # Re-queue unsent data up to 2 attempts, then discard
        max_retries = 2
        for data in data_to_send:
            attempt = getattr(data, "_send_attempts", 0) + 1
            if attempt < max_retries:
                data._send_attempts = attempt
                self._queue.put(data)
            else:
                _logger.warning(
                    "AppInsights send: discarding item after %d failed attempts",
                    attempt,
                )


class _AppInsightsEventClient:
    """Application Insights SDK client for sending custom events.

    This uses the applicationinsights SDK to send events directly to the
    customEvents table in Application Insights.
    """

    _initialized = False
    _client: Optional[Any] = None
    _atexit_registered = False
    _connection_string_provider: ClassVar[Optional[Callable[[], Optional[str]]]] = None

    @staticmethod
    def set_connection_string_provider(
        provider: Callable[[], Optional[str]],
    ) -> None:
        """Override how the connection string is resolved.

        Args:
            provider: Zero-arg callable returning a connection string or None.
        """
        _AppInsightsEventClient._connection_string_provider = provider

    @staticmethod
    def _initialize() -> None:
        """Initialize Application Insights client for custom events."""
        if _AppInsightsEventClient._initialized:
            return

        _AppInsightsEventClient._initialized = True

        # Suppress verbose logging from Application Insights SDK
        # The SDK logs telemetry ingestion details which should not be user-facing
        getLogger("applicationinsights").setLevel(WARNING)
        getLogger("applicationinsights.channel").setLevel(WARNING)

        if not _HAS_APPINSIGHTS:
            return

        if _AppInsightsEventClient._connection_string_provider:
            connection_string = _AppInsightsEventClient._connection_string_provider()
        else:
            connection_string = _get_connection_string()
        if not connection_string:
            return

        try:
            parsed = _parse_connection_string(connection_string)
            if not parsed:
                return

            instrumentation_key = parsed["InstrumentationKey"]
            ingestion_endpoint = parsed.get("IngestionEndpoint")

            # Build custom channel: DiagnosticSender → SynchronousQueue → TelemetryChannel
            if ingestion_endpoint:
                endpoint_url = ingestion_endpoint.rstrip("/") + "/v2/track"
            else:
                endpoint_url = None  # SDK default

            sender = _DiagnosticSender(service_endpoint_uri=endpoint_url)
            queue = SynchronousQueue(sender)
            channel = TelemetryChannel(queue=queue)

            _AppInsightsEventClient._client = AppInsightsTelemetryClient(
                instrumentation_key, telemetry_channel=channel
            )

            # Set application version
            _AppInsightsEventClient._client.context.application.ver = version("uipath")
        except Exception as e:
            # Log but don't raise - telemetry should never break the main application
            _logger.warning(f"Failed to initialize Application Insights client: {e}")
            _logger.debug("Application Insights initialization error", exc_info=True)

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
        except Exception as e:
            # Log but don't raise - telemetry should never break the main application
            _logger.warning(f"Failed to track event '{name}': {e}")
            _logger.debug(f"Event tracking error for '{name}'", exc_info=True)

    @staticmethod
    def flush() -> None:
        """Flush any pending telemetry events."""
        if _AppInsightsEventClient._client:
            try:
                _AppInsightsEventClient._client.flush()
                # Check if items remain after flush (indicates send failure)
                try:
                    remaining = (
                        _AppInsightsEventClient._client.channel.queue._queue.qsize()
                    )
                    if remaining > 0:
                        _logger.warning(
                            "AppInsights flush: %d items still in queue after flush",
                            remaining,
                        )
                except Exception:
                    pass
            except Exception as e:
                # Log but don't raise - telemetry should never break the main application
                _logger.warning(f"Failed to flush telemetry events: {e}")
                _logger.debug("Telemetry flush error", exc_info=True)

    @staticmethod
    def register_atexit_flush() -> None:
        """Register an atexit handler to flush events on process exit."""
        if not _AppInsightsEventClient._atexit_registered:
            atexit.register(_AppInsightsEventClient.flush)
            _AppInsightsEventClient._atexit_registered = True

    @staticmethod
    def reset() -> None:
        """Flush pending events and reset so the next call re-initializes."""
        _AppInsightsEventClient.flush()
        _AppInsightsEventClient._client = None
        _AppInsightsEventClient._initialized = False


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

            # Suppress verbose logging from telemetry libraries
            getLogger("azure").setLevel(WARNING)
            getLogger("applicationinsights").setLevel(WARNING)
            getLogger("opentelemetry").setLevel(WARNING)
            _logger.addHandler(_AzureMonitorOpenTelemetryEventHandler())
            _logger.setLevel(INFO)

            _TelemetryClient._initialized = True
        except Exception as e:
            # Log but don't raise - telemetry should never break the main application
            _logger.warning(f"Failed to initialize telemetry client: {e}")
            _logger.debug("Telemetry initialization error", exc_info=True)

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
            # Safety net: register atexit flush so events are sent even if
            # the caller never explicitly flushes (e.g. serverless containers).
            # Idempotent — only registers once.
            _AppInsightsEventClient.register_atexit_flush()
        except Exception as e:
            # Log but don't raise - telemetry should never break the main application
            _logger.warning(f"Failed to track event '{name}': {e}")
            _logger.debug(f"Event tracking error for '{name}'", exc_info=True)


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


def set_event_connection_string_provider(
    provider: Callable[[], Optional[str]],
) -> None:
    """Override how the Application Insights connection string is resolved.

    Args:
        provider: Zero-arg callable returning a connection string or None.
    """
    _AppInsightsEventClient.set_connection_string_provider(provider)


def reset_event_client() -> None:
    """Flush pending events and reset so the next ``track_event`` re-initializes."""
    _AppInsightsEventClient.reset()


def track_cli_event(
    name: str,
    properties: Optional[Dict[str, Any]] = None,
) -> None:
    """Track a CLI event.

    Buffers the event and registers an atexit handler to flush pending events on process exit.
    """
    if not _TelemetryClient._is_enabled():
        return
    try:
        _AppInsightsEventClient.track_event(name, properties)
        _AppInsightsEventClient.register_atexit_flush()
    except Exception:
        pass


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
