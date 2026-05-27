"""Tests for SocketIOChatBridge and get_chat_bridge."""

import asyncio
import logging
from datetime import datetime
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from uipath._cli._chat._bridge import SocketIOChatBridge, get_chat_bridge
from uipath._cli._debug._bridge import SignalRDebugBridge
from uipath.core.triggers import UiPathApiTrigger, UiPathResumeTrigger


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


class TestSignalRDebugBridgeSendMethod:
    """Tests for SignalRDebugBridge."""

    @pytest.mark.anyio
    async def test_send_with_datetime_does_not_raise(self) -> None:
        """_send method handles datetime objects without raising exceptions."""
        bridge = SignalRDebugBridge(
            hub_url="wss://test.example.com/signalr",
            access_token="test-token",
            headers={},
        )

        mock_client = MagicMock()
        mock_client.send = AsyncMock()
        bridge._client = mock_client

        test_data = {
            "timestamp": datetime(2024, 1, 15, 10, 30, 45),
            "message": "test message",
            "nested": {
                "created_at": datetime(2024, 1, 15, 11, 0, 0),
            },
        }

        await bridge._send("TestEvent", test_data)

        assert mock_client.send.called
        call_args = mock_client.send.call_args

        assert call_args.kwargs["method"] == "SendCommand"

        arguments = call_args.kwargs["arguments"]
        assert len(arguments) == 2
        assert arguments[0] == "TestEvent"

        import json

        parsed_data = json.loads(arguments[1])
        assert "timestamp" in parsed_data
        assert "message" in parsed_data
        assert parsed_data["message"] == "test message"
        assert isinstance(parsed_data["timestamp"], str)
        assert isinstance(parsed_data["nested"]["created_at"], str)


class TestEmitInterruptEvent:
    """Tests for emit_interrupt_event (executingToolCall emission)."""

    def _make_bridge(self) -> SocketIOChatBridge:
        bridge = SocketIOChatBridge(
            websocket_url="wss://test.example.com",
            websocket_path="/socket.io",
            conversation_id="conv-123",
            exchange_id="exch-456",
            headers={},
        )
        bridge._current_message_id = "msg-100"
        return bridge

    def _make_trigger(self, request: dict[str, Any] | None) -> "UiPathResumeTrigger":

        api_resume = UiPathApiTrigger(request=request) if request is not None else None
        return UiPathResumeTrigger(api_resume=api_resume)

    @pytest.mark.anyio
    async def test_execution_phase_emits_executing_tool_call(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An execution-phase trigger emits an executingToolCall event with correct payload."""
        monkeypatch.setenv("CAS_WEBSOCKET_DISABLED", "true")
        bridge = self._make_bridge()
        await bridge.connect()

        emitted_events: list[Any] = []
        original_emit = bridge.emit_message_event

        async def capture_emit(event: Any) -> None:
            emitted_events.append(event)
            await original_emit(event)

        bridge.emit_message_event = capture_emit  # type: ignore[assignment]

        trigger = self._make_trigger(
            {
                "is_execution_phase": True,
                "tool_call_id": "tc-42",
                "tool_name": "my_tool",
                "input": {"key": "value"},
            }
        )

        await bridge.emit_interrupt_event(trigger)

        assert len(emitted_events) == 1
        event = emitted_events[0]
        assert event.message_id == "msg-100"
        assert event.tool_call is not None
        assert event.tool_call.tool_call_id == "tc-42"
        assert event.tool_call.executing is not None
        assert event.tool_call.executing.input == {"key": "value"}

    @pytest.mark.anyio
    async def test_non_execution_phase_does_not_emit(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A trigger without is_execution_phase does not emit any event."""
        monkeypatch.setenv("CAS_WEBSOCKET_DISABLED", "true")
        bridge = self._make_bridge()
        await bridge.connect()

        emitted_events: list[Any] = []
        original_emit = bridge.emit_message_event

        async def capture_emit(event: Any) -> None:
            emitted_events.append(event)
            await original_emit(event)

        bridge.emit_message_event = capture_emit  # type: ignore[assignment]

        trigger = self._make_trigger(
            {
                "is_execution_phase": False,
                "tool_call_id": "tc-42",
                "tool_name": "my_tool",
            }
        )

        await bridge.emit_interrupt_event(trigger)

        assert len(emitted_events) == 0

    @pytest.mark.anyio
    async def test_missing_tool_call_id_does_not_emit(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A trigger missing tool_call_id does not emit."""
        monkeypatch.setenv("CAS_WEBSOCKET_DISABLED", "true")
        bridge = self._make_bridge()
        await bridge.connect()

        emitted_events: list[Any] = []
        original_emit = bridge.emit_message_event

        async def capture_emit(event: Any) -> None:
            emitted_events.append(event)
            await original_emit(event)

        bridge.emit_message_event = capture_emit  # type: ignore[assignment]

        trigger = self._make_trigger(
            {
                "is_execution_phase": True,
                "tool_name": "my_tool",
            }
        )

        await bridge.emit_interrupt_event(trigger)

        assert len(emitted_events) == 0

    @pytest.mark.anyio
    async def test_no_api_resume_does_not_emit(self) -> None:
        """A trigger with no api_resume does not emit."""
        bridge = self._make_bridge()

        emitted_events: list[Any] = []

        async def capture_emit(event: Any) -> None:
            emitted_events.append(event)

        bridge.emit_message_event = capture_emit  # type: ignore[assignment]

        trigger = self._make_trigger(None)

        await bridge.emit_interrupt_event(trigger)

        assert len(emitted_events) == 0


class TestWaitForResumeEndToolCall:
    """Tests for wait_for_resume unblocking on endToolCall events."""

    @pytest.mark.anyio
    async def test_end_tool_call_unblocks_wait_for_resume(self) -> None:
        """Receiving an endToolCall event unblocks wait_for_resume and returns parsed payload."""
        bridge = SocketIOChatBridge(
            websocket_url="wss://test.example.com",
            websocket_path="/socket.io",
            conversation_id="conv-123",
            exchange_id="exch-456",
            headers={},
        )

        end_event = {
            "conversationId": "conv-123",
            "exchange": {
                "exchangeId": "exch-456",
                "message": {
                    "messageId": "msg-200",
                    "toolCall": {
                        "toolCallId": "tc-99",
                        "endToolCall": {
                            "output": {"result": "ok"},
                            "isError": False,
                        },
                    },
                },
            },
        }

        async def simulate_end_event() -> None:
            await asyncio.sleep(0.05)
            await bridge._handle_conversation_event(end_event, "sid-1")

        task = asyncio.create_task(simulate_end_event())
        result = await bridge.wait_for_resume()
        await task

        assert result["output"] == {"result": "ok"}
        assert result["is_error"] is False

    @pytest.mark.anyio
    async def test_confirm_tool_call_unblocks_wait_for_resume(self) -> None:
        """Receiving a confirmToolCall event also unblocks wait_for_resume."""
        bridge = SocketIOChatBridge(
            websocket_url="wss://test.example.com",
            websocket_path="/socket.io",
            conversation_id="conv-123",
            exchange_id="exch-456",
            headers={},
        )

        confirm_event = {
            "conversationId": "conv-123",
            "exchange": {
                "exchangeId": "exch-456",
                "message": {
                    "messageId": "msg-200",
                    "toolCall": {
                        "toolCallId": "tc-99",
                        "confirmToolCall": {
                            "approved": True,
                            "input": {"edited": "data"},
                        },
                    },
                },
            },
        }

        async def simulate_confirm_event() -> None:
            await asyncio.sleep(0.05)
            await bridge._handle_conversation_event(confirm_event, "sid-1")

        task = asyncio.create_task(simulate_confirm_event())
        result = await bridge.wait_for_resume()
        await task

        assert result["approved"] is True
        assert result["input"] == {"edited": "data"}

    @pytest.mark.anyio
    async def test_early_end_tool_call_is_not_lost(self) -> None:
        """An endToolCall that arrives before wait_for_resume is called must not be lost."""
        bridge = SocketIOChatBridge(
            websocket_url="wss://test.example.com",
            websocket_path="/socket.io",
            conversation_id="conv-123",
            exchange_id="exch-456",
            headers={},
        )

        end_event = {
            "conversationId": "conv-123",
            "exchange": {
                "exchangeId": "exch-456",
                "message": {
                    "messageId": "msg-300",
                    "toolCall": {
                        "toolCallId": "tc-100",
                        "endToolCall": {
                            "output": {"early": True},
                            "isError": False,
                        },
                    },
                },
            },
        }

        # Simulate the event arriving BEFORE wait_for_resume is called
        await bridge._handle_conversation_event(end_event, "sid-1")

        result = await bridge.wait_for_resume()

        assert result["output"] == {"early": True}
        assert result["is_error"] is False
