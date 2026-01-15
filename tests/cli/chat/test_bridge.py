"""Tests for SocketIOChatBridge and get_chat_bridge."""

import logging
from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from uipath._cli._chat._bridge import SocketIOChatBridge, get_chat_bridge


class MockRuntimeContext:
    """Mock UiPathRuntimeContext for testing."""

    def __init__(
        self,
        conversation_id: str = "test-conversation-id",
        exchange_id: str = "test-exchange-id",
        tenant_id: str = "test-tenant-id",
        org_id: str = "test-org-id",
    ):
        self.conversation_id = conversation_id
        self.exchange_id = exchange_id
        self.tenant_id = tenant_id
        self.org_id = org_id


class TestSocketIOChatBridgeDebugMode:
    """Tests for SocketIOChatBridge debug mode (CAS_WEBSOCKET_DISABLED)."""

    def test_websocket_disabled_flag_set_from_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """CAS_WEBSOCKET_DISABLED=true sets _websocket_disabled flag."""
        monkeypatch.setenv("CAS_WEBSOCKET_DISABLED", "true")

        bridge = SocketIOChatBridge(
            websocket_url="wss://test.example.com",
            websocket_path="/socket.io",
            conversation_id="conv-123",
            exchange_id="exch-456",
            headers={},
        )

        assert bridge._websocket_disabled is True

    def test_websocket_disabled_flag_false_by_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_websocket_disabled is False when env var not set."""
        monkeypatch.delenv("CAS_WEBSOCKET_DISABLED", raising=False)

        bridge = SocketIOChatBridge(
            websocket_url="wss://test.example.com",
            websocket_path="/socket.io",
            conversation_id="conv-123",
            exchange_id="exch-456",
            headers={},
        )

        assert bridge._websocket_disabled is False

    def test_websocket_disabled_flag_false_when_not_true(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_websocket_disabled is False when env var is not 'true'."""
        monkeypatch.setenv("CAS_WEBSOCKET_DISABLED", "false")

        bridge = SocketIOChatBridge(
            websocket_url="wss://test.example.com",
            websocket_path="/socket.io",
            conversation_id="conv-123",
            exchange_id="exch-456",
            headers={},
        )

        assert bridge._websocket_disabled is False

    @pytest.mark.anyio
    async def test_websocket_disabled_connect_logs_warning(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """With CAS_WEBSOCKET_DISABLED=true, connect() logs warning but doesn't connect."""
        monkeypatch.setenv("CAS_WEBSOCKET_DISABLED", "true")

        bridge = SocketIOChatBridge(
            websocket_url="wss://test.example.com",
            websocket_path="/socket.io",
            conversation_id="conv-123",
            exchange_id="exch-456",
            headers={},
        )

        with caplog.at_level(logging.WARNING):
            await bridge.connect()

        assert "debug mode" in caplog.text.lower()
        assert "not connecting" in caplog.text.lower()
        # Client should be created but not connected
        assert bridge._client is not None
        assert not bridge._connected_event.is_set()


class TestGetChatBridgeCustomHost:
    """Tests for get_chat_bridge with CAS_WEBSOCKET_HOST environment variable."""

    def test_custom_websocket_host_env_var(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """CAS_WEBSOCKET_HOST overrides websocket URL to ws:// scheme."""
        monkeypatch.setenv("UIPATH_URL", "https://cloud.uipath.com/org/tenant")
        monkeypatch.setenv("UIPATH_ACCESS_TOKEN", "test-token")
        monkeypatch.setenv("CAS_WEBSOCKET_HOST", "localhost:8080")

        context = MockRuntimeContext()

        bridge = cast(SocketIOChatBridge, get_chat_bridge(cast(Any, context)))

        assert "ws://localhost:8080" in bridge.websocket_url
        assert "wss://" not in bridge.websocket_url

    def test_custom_websocket_host_uses_simple_path(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Custom host uses /socket.io path instead of full path."""
        monkeypatch.setenv("UIPATH_URL", "https://cloud.uipath.com/org/tenant")
        monkeypatch.setenv("UIPATH_ACCESS_TOKEN", "test-token")
        monkeypatch.setenv("CAS_WEBSOCKET_HOST", "localhost:8080")

        context = MockRuntimeContext()

        bridge = cast(SocketIOChatBridge, get_chat_bridge(cast(Any, context)))

        assert bridge.websocket_path == "/socket.io"

    def test_default_websocket_url_without_custom_host(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Default URL construction without CAS_WEBSOCKET_HOST."""
        monkeypatch.setenv("UIPATH_URL", "https://cloud.uipath.com/org/tenant")
        monkeypatch.setenv("UIPATH_ACCESS_TOKEN", "test-token")
        monkeypatch.delenv("CAS_WEBSOCKET_HOST", raising=False)

        context = MockRuntimeContext(conversation_id="conv-abc")

        bridge = cast(SocketIOChatBridge, get_chat_bridge(cast(Any, context)))

        assert "wss://cloud.uipath.com" in bridge.websocket_url
        assert "conversationId=conv-abc" in bridge.websocket_url
        assert bridge.websocket_path == "autopilotforeveryone_/websocket_/socket.io"

    def test_get_chat_bridge_includes_conversation_id_in_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Conversation ID is included in websocket URL."""
        monkeypatch.setenv("UIPATH_URL", "https://cloud.uipath.com/org/tenant")
        monkeypatch.setenv("UIPATH_ACCESS_TOKEN", "test-token")
        monkeypatch.delenv("CAS_WEBSOCKET_HOST", raising=False)

        context = MockRuntimeContext(conversation_id="my-conversation-id")

        bridge = cast(SocketIOChatBridge, get_chat_bridge(cast(Any, context)))

        assert "conversationId=my-conversation-id" in bridge.websocket_url


class TestGetChatBridge:
    """Tests for get_chat_bridge factory function."""

    def test_get_chat_bridge_returns_socket_io_bridge(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Returns SocketIOChatBridge instance."""
        monkeypatch.setenv("UIPATH_URL", "https://cloud.uipath.com/org/tenant")
        monkeypatch.setenv("UIPATH_ACCESS_TOKEN", "test-token")

        context = MockRuntimeContext()

        bridge = get_chat_bridge(cast(Any, context))

        assert isinstance(bridge, SocketIOChatBridge)

    def test_get_chat_bridge_constructs_correct_headers(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Headers include Authorization and other required fields."""
        monkeypatch.setenv("UIPATH_URL", "https://cloud.uipath.com/org/tenant")
        monkeypatch.setenv("UIPATH_ACCESS_TOKEN", "my-access-token")

        context = MockRuntimeContext(
            tenant_id="tenant-123",
            org_id="org-456",
            conversation_id="conv-789",
        )

        bridge = cast(SocketIOChatBridge, get_chat_bridge(cast(Any, context)))

        assert "Authorization" in bridge.headers
        assert "Bearer my-access-token" in bridge.headers["Authorization"]
        assert "X-UiPath-Internal-TenantId" in bridge.headers
        assert "X-UiPath-Internal-AccountId" in bridge.headers
        assert "X-UiPath-ConversationId" in bridge.headers
        assert bridge.headers["X-UiPath-ConversationId"] == "conv-789"

    def test_get_chat_bridge_raises_without_uipath_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Raises RuntimeError if UIPATH_URL is not set."""
        monkeypatch.delenv("UIPATH_URL", raising=False)

        context = MockRuntimeContext()

        with pytest.raises(RuntimeError) as exc_info:
            get_chat_bridge(cast(Any, context))

        assert "UIPATH_URL" in str(exc_info.value)

    def test_get_chat_bridge_raises_with_invalid_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Raises RuntimeError if UIPATH_URL is invalid."""
        monkeypatch.setenv("UIPATH_URL", "not-a-valid-url")

        context = MockRuntimeContext()

        with pytest.raises(RuntimeError) as exc_info:
            get_chat_bridge(cast(Any, context))

        assert "Invalid UIPATH_URL" in str(exc_info.value)

    def test_get_chat_bridge_sets_exchange_id(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Exchange ID from context is set on bridge."""
        monkeypatch.setenv("UIPATH_URL", "https://cloud.uipath.com/org/tenant")
        monkeypatch.setenv("UIPATH_ACCESS_TOKEN", "test-token")

        context = MockRuntimeContext(exchange_id="my-exchange-id")

        bridge = cast(SocketIOChatBridge, get_chat_bridge(cast(Any, context)))

        assert bridge.exchange_id == "my-exchange-id"

    def test_get_chat_bridge_sets_conversation_id(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Conversation ID from context is set on bridge."""
        monkeypatch.setenv("UIPATH_URL", "https://cloud.uipath.com/org/tenant")
        monkeypatch.setenv("UIPATH_ACCESS_TOKEN", "test-token")

        context = MockRuntimeContext(conversation_id="my-conversation-id")

        bridge = cast(SocketIOChatBridge, get_chat_bridge(cast(Any, context)))

        assert bridge.conversation_id == "my-conversation-id"


class TestSocketIOChatBridgeConnectionStates:
    """Tests for SocketIOChatBridge connection state handling."""

    def test_is_connected_false_initially(self) -> None:
        """is_connected is False before connecting."""
        bridge = SocketIOChatBridge(
            websocket_url="wss://test.example.com",
            websocket_path="/socket.io",
            conversation_id="conv-123",
            exchange_id="exch-456",
            headers={},
        )

        assert bridge.is_connected is False

    @pytest.mark.anyio
    async def test_emit_message_raises_without_client(self) -> None:
        """emit_message_event raises RuntimeError if client not initialized."""
        bridge = SocketIOChatBridge(
            websocket_url="wss://test.example.com",
            websocket_path="/socket.io",
            conversation_id="conv-123",
            exchange_id="exch-456",
            headers={},
        )

        mock_message_event = MagicMock()
        mock_message_event.message_id = "msg-123"

        with pytest.raises(RuntimeError) as exc_info:
            await bridge.emit_message_event(mock_message_event)

        assert "not connected" in str(exc_info.value).lower()

    @pytest.mark.anyio
    async def test_emit_exchange_end_raises_without_client(self) -> None:
        """emit_exchange_end_event raises RuntimeError if client not initialized."""
        bridge = SocketIOChatBridge(
            websocket_url="wss://test.example.com",
            websocket_path="/socket.io",
            conversation_id="conv-123",
            exchange_id="exch-456",
            headers={},
        )

        with pytest.raises(RuntimeError) as exc_info:
            await bridge.emit_exchange_end_event()

        assert "not connected" in str(exc_info.value).lower()
