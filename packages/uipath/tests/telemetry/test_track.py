"""Tests for telemetry tracking functionality."""

import os
from unittest.mock import MagicMock, patch

from uipath.telemetry._track import (
    _AppInsightsEventClient,
    _DiagnosticSender,
    _parse_connection_string,
    _TelemetryClient,
    flush_events,
    is_telemetry_enabled,
    reset_event_client,
    set_event_connection_string_provider,
    track,
    track_event,
)


class TestParseConnectionString:
    """Test connection string parsing functionality."""

    def test_parse_valid_connection_string(self):
        """Test parsing a valid Application Insights connection string."""
        connection_string = (
            "InstrumentationKey=test-key-123;"
            "IngestionEndpoint=https://example.com/;"
            "LiveEndpoint=https://live.example.com/"
        )

        result = _parse_connection_string(connection_string)

        assert result == {
            "InstrumentationKey": "test-key-123",
            "IngestionEndpoint": "https://example.com/",
        }

    def test_parse_connection_string_only_instrumentation_key(self):
        """Test parsing connection string with only InstrumentationKey."""
        connection_string = "InstrumentationKey=simple-key"

        result = _parse_connection_string(connection_string)

        assert result == {"InstrumentationKey": "simple-key"}

    def test_parse_connection_string_missing_instrumentation_key(self):
        """Test parsing connection string without InstrumentationKey."""
        connection_string = (
            "IngestionEndpoint=https://example.com/;"
            "LiveEndpoint=https://live.example.com/"
        )

        result = _parse_connection_string(connection_string)

        assert result is None

    def test_parse_malformed_connection_string(self):
        """Test parsing malformed connection string."""
        connection_string = "not-a-valid-connection-string"

        result = _parse_connection_string(connection_string)

        assert result is None

    def test_parse_empty_connection_string(self):
        """Test parsing empty connection string."""
        result = _parse_connection_string("")

        assert result is None

    def test_parse_connection_string_with_special_chars_in_value(self):
        """Test parsing connection string with special characters in value."""
        connection_string = "InstrumentationKey=key=with=equals;Other=value"

        result = _parse_connection_string(connection_string)

        assert result == {"InstrumentationKey": "key=with=equals"}


class TestAppInsightsEventClient:
    """Test _AppInsightsEventClient functionality."""

    def setup_method(self):
        """Reset AppInsightsEventClient state before each test."""
        _AppInsightsEventClient._initialized = False
        _AppInsightsEventClient._client = None
        _AppInsightsEventClient._connection_string_provider = None

    def teardown_method(self):
        """Clean up after each test."""
        _AppInsightsEventClient._initialized = False
        _AppInsightsEventClient._client = None
        _AppInsightsEventClient._connection_string_provider = None

    @patch("uipath.telemetry._track._CONNECTION_STRING", "$CONNECTION_STRING")
    def test_initialize_no_connection_string(self):
        """Test initialization when no connection string is provided."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove TELEMETRY_CONNECTION_STRING if it exists
            os.environ.pop("TELEMETRY_CONNECTION_STRING", None)

            _AppInsightsEventClient._initialize()

            assert _AppInsightsEventClient._initialized is True
            assert _AppInsightsEventClient._client is None

    @patch("uipath.telemetry._track.TelemetryChannel")
    @patch("uipath.telemetry._track.SynchronousQueue")
    @patch("uipath.telemetry._track._DiagnosticSender")
    @patch("uipath.telemetry._track._HAS_APPINSIGHTS", True)
    @patch("uipath.telemetry._track.AppInsightsTelemetryClient")
    @patch(
        "uipath.telemetry._track._CONNECTION_STRING",
        "InstrumentationKey=builtin-key;IngestionEndpoint=https://example.com/",
    )
    def test_initialize_falls_back_to_builtin_connection_string(
        self, mock_client_class, mock_sender_class, mock_queue_class, mock_channel_class
    ):
        """Test initialization uses _CONNECTION_STRING when env var is not set."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("TELEMETRY_CONNECTION_STRING", None)

            _AppInsightsEventClient._initialize()

        assert _AppInsightsEventClient._initialized is True
        assert _AppInsightsEventClient._client is mock_client
        mock_sender_class.assert_called_once_with(
            service_endpoint_uri="https://example.com/v2/track"
        )
        mock_client_class.assert_called_once_with(
            "builtin-key", telemetry_channel=mock_channel_class.return_value
        )

    @patch("uipath.telemetry._track._HAS_APPINSIGHTS", False)
    def test_initialize_no_appinsights_package(self):
        """Test initialization when applicationinsights package is not available."""
        _AppInsightsEventClient._initialize()

        assert _AppInsightsEventClient._initialized is True
        assert _AppInsightsEventClient._client is None

    @patch("uipath.telemetry._track.TelemetryChannel")
    @patch("uipath.telemetry._track.SynchronousQueue")
    @patch("uipath.telemetry._track._DiagnosticSender")
    @patch("uipath.telemetry._track._HAS_APPINSIGHTS", True)
    @patch("uipath.telemetry._track.AppInsightsTelemetryClient")
    def test_initialize_creates_client(
        self, mock_client_class, mock_sender_class, mock_queue_class, mock_channel_class
    ):
        """Test that initialization creates Application Insights client."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        with patch.dict(
            os.environ,
            {
                "TELEMETRY_CONNECTION_STRING": (
                    "InstrumentationKey=test-key;IngestionEndpoint=https://example.com/"
                )
            },
        ):
            _AppInsightsEventClient._initialize()

        assert _AppInsightsEventClient._initialized is True
        assert _AppInsightsEventClient._client is mock_client
        mock_sender_class.assert_called_once_with(
            service_endpoint_uri="https://example.com/v2/track"
        )
        mock_client_class.assert_called_once_with(
            "test-key", telemetry_channel=mock_channel_class.return_value
        )

    @patch("uipath.telemetry._track._DiagnosticSender")
    @patch("uipath.telemetry._track._HAS_APPINSIGHTS", True)
    @patch("uipath.telemetry._track.AppInsightsTelemetryClient")
    def test_initialize_invalid_connection_string(
        self, mock_client_class, mock_sender_class
    ):
        """Test initialization with invalid connection string."""
        with patch.dict(
            os.environ,
            {"TELEMETRY_CONNECTION_STRING": "invalid-connection-string"},
        ):
            _AppInsightsEventClient._initialize()

        assert _AppInsightsEventClient._initialized is True
        assert _AppInsightsEventClient._client is None
        mock_client_class.assert_not_called()

    def test_initialize_only_once(self):
        """Test that initialization only happens once."""
        _AppInsightsEventClient._initialized = True
        _AppInsightsEventClient._client = "existing_client"

        _AppInsightsEventClient._initialize()

        # Should not change the client since already initialized
        assert _AppInsightsEventClient._client == "existing_client"

    @patch("uipath.telemetry._track._HAS_APPINSIGHTS", True)
    @patch("uipath.telemetry._track.AppInsightsTelemetryClient")
    def test_track_event_calls_client(self, mock_client_class):
        """Test that track_event calls the Application Insights client."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        _AppInsightsEventClient._initialized = True
        _AppInsightsEventClient._client = mock_client

        properties = {"key1": "value1", "key2": 123, "key3": None}

        _AppInsightsEventClient.track_event("test_event", properties)

        mock_client.track_event.assert_called_once_with(
            name="test_event",
            properties={
                "key1": "value1",
                "key2": "123",
            },  # None filtered, int converted
            measurements={},
        )

    def test_track_event_no_client(self):
        """Test that track_event does nothing when client is not initialized."""
        _AppInsightsEventClient._initialized = True
        _AppInsightsEventClient._client = None

        # Should not raise any exception
        _AppInsightsEventClient.track_event("test_event", {"key": "value"})

    def test_track_event_empty_properties(self):
        """Test track_event with empty properties."""
        mock_client = MagicMock()
        _AppInsightsEventClient._initialized = True
        _AppInsightsEventClient._client = mock_client

        _AppInsightsEventClient.track_event("test_event", None)

        mock_client.track_event.assert_called_once_with(
            name="test_event",
            properties={},
            measurements={},
        )

    def test_flush_calls_client(self):
        """Test that flush calls the client's flush method."""
        mock_client = MagicMock()
        _AppInsightsEventClient._client = mock_client

        _AppInsightsEventClient.flush()

        mock_client.flush.assert_called_once()

    def test_flush_no_client(self):
        """Test that flush does nothing when client is not available."""
        _AppInsightsEventClient._client = None

        # Should not raise any exception
        _AppInsightsEventClient.flush()

    @patch("uipath.telemetry._track.TelemetryChannel")
    @patch("uipath.telemetry._track.SynchronousQueue")
    @patch("uipath.telemetry._track._DiagnosticSender")
    @patch("uipath.telemetry._track._HAS_APPINSIGHTS", True)
    @patch("uipath.telemetry._track.AppInsightsTelemetryClient")
    def test_connection_string_provider_overrides_default(
        self, mock_client_class, mock_sender_class, mock_queue_class, mock_channel_class
    ):
        """Test that a custom provider is used instead of _get_connection_string."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        def provider() -> str:
            return (
                "InstrumentationKey=from-provider;IngestionEndpoint=https://custom.com/"
            )

        _AppInsightsEventClient.set_connection_string_provider(provider)

        _AppInsightsEventClient._initialize()

        assert _AppInsightsEventClient._client is mock_client
        mock_client_class.assert_called_once_with(
            "from-provider", telemetry_channel=mock_channel_class.return_value
        )
        mock_sender_class.assert_called_once_with(
            service_endpoint_uri="https://custom.com/v2/track"
        )

    @patch("uipath.telemetry._track._HAS_APPINSIGHTS", True)
    def test_connection_string_provider_returning_none_skips_client(self):
        """Test that provider returning None results in no client."""
        _AppInsightsEventClient.set_connection_string_provider(lambda: None)

        _AppInsightsEventClient._initialize()

        assert _AppInsightsEventClient._initialized is True
        assert _AppInsightsEventClient._client is None

    @patch("uipath.telemetry._track.TelemetryChannel")
    @patch("uipath.telemetry._track.SynchronousQueue")
    @patch("uipath.telemetry._track._DiagnosticSender")
    @patch("uipath.telemetry._track._HAS_APPINSIGHTS", True)
    @patch("uipath.telemetry._track.AppInsightsTelemetryClient")
    @patch(
        "uipath.telemetry._track._CONNECTION_STRING",
        "InstrumentationKey=builtin-key",
    )
    def test_provider_bypasses_builtin_fallback(
        self, mock_client_class, mock_sender_class, mock_queue_class, mock_channel_class
    ):
        """Test that provider prevents fallback to _CONNECTION_STRING."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        _AppInsightsEventClient.set_connection_string_provider(
            lambda: "InstrumentationKey=provider-key"
        )

        with patch.dict(os.environ, {}, clear=True):
            _AppInsightsEventClient._initialize()

        # Should use provider-key, not builtin-key
        mock_client_class.assert_called_once_with(
            "provider-key", telemetry_channel=mock_channel_class.return_value
        )

    def test_reset_clears_initialized_and_client(self):
        """Test that reset clears initialized flag and client."""
        _AppInsightsEventClient._initialized = True
        _AppInsightsEventClient._client = MagicMock()

        _AppInsightsEventClient.reset()

        assert _AppInsightsEventClient._initialized is False
        assert _AppInsightsEventClient._client is None

    def test_reset_flushes_before_clearing(self):
        """Test that reset flushes pending events before clearing."""
        mock_client = MagicMock()
        _AppInsightsEventClient._initialized = True
        _AppInsightsEventClient._client = mock_client

        _AppInsightsEventClient.reset()

        mock_client.flush.assert_called_once()

    @patch("uipath.telemetry._track.TelemetryChannel")
    @patch("uipath.telemetry._track.SynchronousQueue")
    @patch("uipath.telemetry._track._DiagnosticSender")
    @patch("uipath.telemetry._track._HAS_APPINSIGHTS", True)
    @patch("uipath.telemetry._track.AppInsightsTelemetryClient")
    def test_reset_allows_reinitialization_with_new_connection_string(
        self, mock_client_class, mock_sender_class, mock_queue_class, mock_channel_class
    ):
        """Test that after reset, next initialize reads current env."""
        mock_client_1 = MagicMock()
        mock_client_2 = MagicMock()
        mock_client_class.side_effect = [mock_client_1, mock_client_2]

        # First init with connection string A
        with patch.dict(
            os.environ,
            {"TELEMETRY_CONNECTION_STRING": "InstrumentationKey=key-a"},
        ):
            _AppInsightsEventClient._initialize()

        assert _AppInsightsEventClient._client is mock_client_1

        # Reset
        _AppInsightsEventClient.reset()

        # Second init with connection string B
        with patch.dict(
            os.environ,
            {"TELEMETRY_CONNECTION_STRING": "InstrumentationKey=key-b"},
        ):
            _AppInsightsEventClient._initialize()

        assert _AppInsightsEventClient._client is mock_client_2
        assert mock_client_class.call_count == 2


class TestPublicProviderAndResetFunctions:
    """Test the public set_event_connection_string_provider and reset_event_client."""

    def setup_method(self) -> None:
        """Reset state before each test."""
        _AppInsightsEventClient._initialized = False
        _AppInsightsEventClient._client = None
        _AppInsightsEventClient._connection_string_provider = None

    def teardown_method(self) -> None:
        """Clean up after each test."""
        _AppInsightsEventClient._initialized = False
        _AppInsightsEventClient._client = None
        _AppInsightsEventClient._connection_string_provider = None

    def test_set_event_connection_string_provider_sets_provider(self) -> None:
        """Test that the public function sets the provider on the client."""

        def provider() -> str:
            return "InstrumentationKey=test"

        set_event_connection_string_provider(provider)

        assert _AppInsightsEventClient._connection_string_provider is provider

    def test_reset_event_client_resets_state(self) -> None:
        """Test that the public function resets client state."""
        _AppInsightsEventClient._initialized = True
        _AppInsightsEventClient._client = MagicMock()

        reset_event_client()

        assert _AppInsightsEventClient._initialized is False
        assert _AppInsightsEventClient._client is None


class TestTelemetryClient:
    """Test _TelemetryClient functionality."""

    def setup_method(self):
        """Reset TelemetryClient state before each test."""
        _TelemetryClient._initialized = False

    def teardown_method(self):
        """Clean up after each test."""
        _TelemetryClient._initialized = False

    def test_is_enabled_default_true(self):
        """Test that telemetry is enabled by default."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("UIPATH_TELEMETRY_ENABLED", None)

            assert _TelemetryClient._is_enabled() is True

    def test_is_enabled_explicit_true(self):
        """Test telemetry enabled when explicitly set to true."""
        with patch.dict(os.environ, {"UIPATH_TELEMETRY_ENABLED": "true"}):
            assert _TelemetryClient._is_enabled() is True

    def test_is_enabled_explicit_false(self):
        """Test telemetry disabled when set to false."""
        with patch.dict(os.environ, {"UIPATH_TELEMETRY_ENABLED": "false"}):
            assert _TelemetryClient._is_enabled() is False

    def test_is_enabled_case_insensitive(self):
        """Test that telemetry enabled check is case insensitive."""
        with patch.dict(os.environ, {"UIPATH_TELEMETRY_ENABLED": "TRUE"}):
            assert _TelemetryClient._is_enabled() is True

        with patch.dict(os.environ, {"UIPATH_TELEMETRY_ENABLED": "False"}):
            assert _TelemetryClient._is_enabled() is False

    @patch.object(_TelemetryClient, "_is_enabled", return_value=False)
    def test_track_event_disabled(self, mock_is_enabled):
        """Test that track_event does nothing when telemetry is disabled."""
        with patch.object(_AppInsightsEventClient, "track_event") as mock_track:
            _TelemetryClient.track_event("test_event", {"key": "value"})

            mock_track.assert_not_called()

    @patch.object(_AppInsightsEventClient, "register_atexit_flush")
    @patch.object(_TelemetryClient, "_is_enabled", return_value=True)
    @patch.object(_AppInsightsEventClient, "track_event")
    def test_track_event_enabled(self, mock_track, mock_is_enabled, mock_atexit):
        """Test that track_event calls AppInsightsEventClient when enabled."""
        properties = {"key": "value"}

        _TelemetryClient.track_event("test_event", properties)

        mock_track.assert_called_once_with("test_event", properties)

    @patch.object(_AppInsightsEventClient, "register_atexit_flush")
    @patch.object(_TelemetryClient, "_is_enabled", return_value=True)
    @patch.object(_AppInsightsEventClient, "track_event")
    def test_track_event_registers_atexit_handler(
        self, mock_track, mock_is_enabled, mock_atexit
    ):
        """Test that track_event registers atexit flush handler."""
        _TelemetryClient.track_event("test_event", {"key": "value"})

        mock_atexit.assert_called_once()


class TestPublicFunctions:
    """Test public telemetry functions."""

    def setup_method(self):
        """Reset state before each test."""
        _TelemetryClient._initialized = False
        _AppInsightsEventClient._initialized = False
        _AppInsightsEventClient._client = None

    @patch.object(_TelemetryClient, "track_event")
    def test_track_event_function(self, mock_track):
        """Test the global track_event function."""
        properties = {"key": "value"}

        track_event("test_event", properties)

        mock_track.assert_called_once_with("test_event", properties)

    @patch.object(_TelemetryClient, "_is_enabled", return_value=True)
    def test_is_telemetry_enabled_true(self, mock_is_enabled):
        """Test is_telemetry_enabled returns True when enabled."""
        assert is_telemetry_enabled() is True

    @patch.object(_TelemetryClient, "_is_enabled", return_value=False)
    def test_is_telemetry_enabled_false(self, mock_is_enabled):
        """Test is_telemetry_enabled returns False when disabled."""
        assert is_telemetry_enabled() is False

    @patch.object(_AppInsightsEventClient, "flush")
    def test_flush_events_function(self, mock_flush):
        """Test the global flush_events function."""
        flush_events()

        mock_flush.assert_called_once()


class TestTrackDecorator:
    """Test the @track decorator functionality."""

    def setup_method(self):
        """Reset state before each test."""
        _TelemetryClient._initialized = False

    @patch.object(_TelemetryClient, "_track_method")
    @patch.object(_TelemetryClient, "_is_enabled", return_value=True)
    def test_track_decorator_with_name(self, mock_is_enabled, mock_track_method):
        """Test @track decorator with explicit name."""

        @track("custom_name")
        def my_function():
            return "result"

        result = my_function()

        assert result == "result"
        mock_track_method.assert_called_once_with("custom_name", None)

    @patch.object(_TelemetryClient, "_track_method")
    @patch.object(_TelemetryClient, "_is_enabled", return_value=True)
    def test_track_decorator_without_name(self, mock_is_enabled, mock_track_method):
        """Test @track decorator without name uses function name."""

        @track
        def my_function():
            return "result"

        result = my_function()

        assert result == "result"
        mock_track_method.assert_called_once_with("my_function", None)

    @patch.object(_TelemetryClient, "_track_method")
    @patch.object(_TelemetryClient, "_is_enabled", return_value=True)
    def test_track_decorator_with_extra(self, mock_is_enabled, mock_track_method):
        """Test @track decorator with extra attributes."""
        extra = {"attr1": "value1"}

        @track("event_name", extra=extra)
        def my_function():
            return "result"

        result = my_function()

        assert result == "result"
        mock_track_method.assert_called_once_with("event_name", extra)

    @patch.object(_TelemetryClient, "_track_method")
    @patch.object(_TelemetryClient, "_is_enabled", return_value=True)
    def test_track_decorator_when_condition_true(
        self, mock_is_enabled, mock_track_method
    ):
        """Test @track decorator with when condition that returns True."""

        @track("event_name", when=True)
        def my_function():
            return "result"

        result = my_function()

        assert result == "result"
        mock_track_method.assert_called_once()

    @patch.object(_TelemetryClient, "_track_method")
    @patch.object(_TelemetryClient, "_is_enabled", return_value=True)
    def test_track_decorator_when_condition_false(
        self, mock_is_enabled, mock_track_method
    ):
        """Test @track decorator with when condition that returns False."""

        @track("event_name", when=False)
        def my_function():
            return "result"

        result = my_function()

        assert result == "result"
        mock_track_method.assert_not_called()

    @patch.object(_TelemetryClient, "_track_method")
    @patch.object(_TelemetryClient, "_is_enabled", return_value=True)
    def test_track_decorator_when_callable(self, mock_is_enabled, mock_track_method):
        """Test @track decorator with callable when condition."""

        @track("event_name", when=lambda x: x > 5)
        def my_function(x):
            return x * 2

        # Should track when x > 5
        result = my_function(10)
        assert result == 20
        mock_track_method.assert_called_once()

        mock_track_method.reset_mock()

        # Should not track when x <= 5
        result = my_function(3)
        assert result == 6
        mock_track_method.assert_not_called()

    @patch.object(_TelemetryClient, "_is_enabled", return_value=False)
    @patch.object(_TelemetryClient, "_initialize")
    def test_track_decorator_telemetry_disabled(self, mock_initialize, mock_is_enabled):
        """Test @track decorator doesn't initialize when telemetry is disabled.

        The decorator still calls _track_method, but _track_method should
        short-circuit and not initialize when telemetry is disabled.
        """

        @track("event_name")
        def my_function():
            return "result"

        result = my_function()

        assert result == "result"
        # _initialize should not be called when telemetry is disabled
        mock_initialize.assert_not_called()

    @patch.object(_TelemetryClient, "_track_method")
    @patch.object(_TelemetryClient, "_is_enabled", return_value=True)
    def test_track_decorator_preserves_function_metadata(
        self, mock_is_enabled, mock_track_method
    ):
        """Test that @track decorator preserves function metadata."""

        @track("event_name")
        def my_function_with_doc():
            """This is a docstring."""
            return "result"

        assert my_function_with_doc.__name__ == "my_function_with_doc"
        assert my_function_with_doc.__doc__ == "This is a docstring."


class TestTelemetryExceptionHandling:
    """Test that telemetry never breaks the main application."""

    def setup_method(self):
        """Reset state before each test."""
        _AppInsightsEventClient._initialized = False
        _AppInsightsEventClient._client = None

    def test_track_event_handles_client_exception(self):
        """Test that track_event handles exceptions from the client."""
        mock_client = MagicMock()
        mock_client.track_event.side_effect = Exception("Client error")
        _AppInsightsEventClient._initialized = True
        _AppInsightsEventClient._client = mock_client

        # Should not raise exception
        _AppInsightsEventClient.track_event("test_event", {"key": "value"})

    def test_flush_handles_exception(self):
        """Test that flush handles exceptions from the client."""
        mock_client = MagicMock()
        mock_client.flush.side_effect = Exception("Flush error")
        _AppInsightsEventClient._client = mock_client

        # Should not raise exception
        _AppInsightsEventClient.flush()

    @patch("uipath.telemetry._track.TelemetryChannel")
    @patch("uipath.telemetry._track.SynchronousQueue")
    @patch("uipath.telemetry._track._DiagnosticSender")
    @patch("uipath.telemetry._track._HAS_APPINSIGHTS", True)
    @patch("uipath.telemetry._track.AppInsightsTelemetryClient")
    def test_initialize_handles_exception(
        self, mock_client_class, mock_sender_class, mock_queue_class, mock_channel_class
    ):
        """Test that initialization handles exceptions."""
        mock_client_class.side_effect = Exception("Init error")

        with patch.dict(
            os.environ,
            {"TELEMETRY_CONNECTION_STRING": "InstrumentationKey=test-key"},
        ):
            # Should not raise exception
            _AppInsightsEventClient._initialize()

        assert _AppInsightsEventClient._initialized is True
        assert _AppInsightsEventClient._client is None


class TestDiagnosticSender:
    """Test _DiagnosticSender retry, re-queue, and discard logic."""

    def _make_sender(self):
        """Create a _DiagnosticSender with a mock queue."""
        sender = _DiagnosticSender.__new__(_DiagnosticSender)
        sender._service_endpoint_uri = "https://example.com/v2/track"
        sender._timeout = 10
        sender._queue = MagicMock()
        return sender

    def _make_data_item(self, send_attempts=None):
        item = MagicMock()
        item.write.return_value = {"name": "test"}
        if send_attempts is not None:
            item._send_attempts = send_attempts
        else:
            del item._send_attempts
        return item

    @patch("urllib.request.urlopen")
    def test_successful_send_does_not_requeue(self, mock_urlopen):
        """Test that a 2xx response returns early without re-queuing."""
        sender = self._make_sender()
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_urlopen.return_value = mock_response

        data = [self._make_data_item()]
        sender.send(data)

        sender._queue.put.assert_not_called()

    @patch("urllib.request.urlopen")
    def test_http_400_discards_without_requeue(self, mock_urlopen):
        """Test that HTTP 400 logs a warning and returns before retry logic."""
        from urllib.error import HTTPError

        sender = self._make_sender()
        mock_urlopen.side_effect = HTTPError(
            url="https://example.com", code=400, msg="Bad Request", hdrs=MagicMock(), fp=None
        )

        data = [self._make_data_item()]
        sender.send(data)

        sender._queue.put.assert_not_called()

    @patch("urllib.request.urlopen")
    def test_multiple_fresh_items_all_requeued_on_failure(self, mock_urlopen):
        """Test that all fresh items in a batch are re-queued on failure."""
        from urllib.error import HTTPError

        sender = self._make_sender()
        mock_urlopen.side_effect = HTTPError(
            url="https://example.com", code=503, msg="Unavailable", hdrs=MagicMock(), fp=None
        )

        items = [self._make_data_item() for _ in range(3)]
        sender.send(items)

        assert sender._queue.put.call_count == 3
        for item in items:
            assert item._send_attempts == 1

    @patch("urllib.request.urlopen")
    def test_item_with_one_prior_attempt_is_discarded(self, mock_urlopen):
        """Test that an already-retried item (attempt=1) is discarded on next failure."""
        from urllib.error import HTTPError

        sender = self._make_sender()
        mock_urlopen.side_effect = HTTPError(
            url="https://example.com", code=500, msg="Server Error", hdrs=MagicMock(), fp=None
        )

        item = self._make_data_item(send_attempts=1)  # already retried once
        sender.send([item])

        sender._queue.put.assert_not_called()

    @patch("urllib.request.urlopen")
    def test_mixed_batch_requeues_fresh_discards_retried(self, mock_urlopen):
        """Test a batch with both fresh and already-retried items."""
        from urllib.error import HTTPError

        sender = self._make_sender()
        mock_urlopen.side_effect = HTTPError(
            url="https://example.com", code=502, msg="Bad Gateway", hdrs=MagicMock(), fp=None
        )

        fresh_item = self._make_data_item()  # no prior attempts
        retried_item = self._make_data_item(send_attempts=1)  # already retried

        sender.send([fresh_item, retried_item])

        sender._queue.put.assert_called_once_with(fresh_item)
        assert fresh_item._send_attempts == 1
