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
        end_exchange: bool = True,
    ):
        self.conversation_id = conversation_id
        self.exchange_id = exchange_id
        self.tenant_id = tenant_id
        self.org_id = org_id
        self.end_exchange = end_exchange


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

    def test_get_chat_bridge_falls_back_to_env_when_tenant_and_org_absent(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Tenant/account headers fall back to env vars when context values are None."""
        monkeypatch.setenv("UIPATH_URL", "https://cloud.uipath.com/org/tenant")
        monkeypatch.setenv("UIPATH_ACCESS_TOKEN", "my-access-token")
        monkeypatch.setenv("UIPATH_TENANT_ID", "env-tenant")
        monkeypatch.setenv("UIPATH_ORGANIZATION_ID", "env-org")

        context = MockRuntimeContext(
            tenant_id=None,  # type: ignore[arg-type]
            org_id=None,  # type: ignore[arg-type]
            conversation_id="conv-789",
        )

        bridge = cast(SocketIOChatBridge, get_chat_bridge(cast(Any, context)))

        assert bridge.headers["X-UiPath-Internal-TenantId"] == "env-tenant"
        assert bridge.headers["X-UiPath-Internal-AccountId"] == "env-org"

    def test_get_chat_bridge_includes_conversational_user_id_header_when_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Conversation owner id (from FpsProperties) is sent on the handshake for CAS to validate."""
        monkeypatch.setenv("UIPATH_URL", "https://cloud.uipath.com/org/tenant")
        monkeypatch.setenv("UIPATH_ACCESS_TOKEN", "my-access-token")

        context = MockRuntimeContext(conversation_id="conv-789")
        context.conversational_user_id = "owner-guid"  # type: ignore[attr-defined]

        bridge = cast(SocketIOChatBridge, get_chat_bridge(cast(Any, context)))

        assert bridge.headers["X-UiPath-Internal-ConversationalUserId"] == "owner-guid"

    def test_get_chat_bridge_omits_conversational_user_id_header_when_absent(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No header is sent when the runtime has no owner id (backward compatible)."""
        monkeypatch.setenv("UIPATH_URL", "https://cloud.uipath.com/org/tenant")
        monkeypatch.setenv("UIPATH_ACCESS_TOKEN", "my-access-token")

        context = MockRuntimeContext(conversation_id="conv-789")

        bridge = cast(SocketIOChatBridge, get_chat_bridge(cast(Any, context)))

        assert "X-UiPath-Internal-ConversationalUserId" not in bridge.headers

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


class TestSocketIOChatBridgeEndExchange:
    """The bridge owns whether to honor the exchange-end event (CAS-specific)."""

    def _make_connected_bridge(self, end_exchange: bool) -> SocketIOChatBridge:
        bridge = SocketIOChatBridge(
            websocket_url="wss://test.example.com",
            websocket_path="/socket.io",
            conversation_id="conv-123",
            exchange_id="exch-456",
            headers={},
            end_exchange=end_exchange,
        )
        bridge._websocket_disabled = False
        bridge._client = AsyncMock()
        bridge._connected_event.set()
        return bridge

    def test_end_exchange_defaults_true(self) -> None:
        bridge = SocketIOChatBridge(
            websocket_url="wss://test.example.com",
            websocket_path="/socket.io",
            conversation_id="conv-123",
            exchange_id="exch-456",
            headers={},
        )
        assert bridge.end_exchange is True

    @pytest.mark.anyio
    async def test_emit_exchange_end_sends_when_end_exchange_true(self) -> None:
        bridge = self._make_connected_bridge(end_exchange=True)

        await bridge.emit_exchange_end_event()

        cast(AsyncMock, bridge._client).emit.assert_awaited_once()
        assert (
            cast(AsyncMock, bridge._client).emit.await_args.args[0]
            == "ConversationEvent"
        )

    @pytest.mark.anyio
    async def test_emit_exchange_end_suppressed_when_end_exchange_false(self) -> None:
        bridge = self._make_connected_bridge(end_exchange=False)

        await bridge.emit_exchange_end_event()

        cast(AsyncMock, bridge._client).emit.assert_not_awaited()

    @pytest.mark.anyio
    async def test_emit_exchange_end_false_does_not_require_client(self) -> None:
        """With the exchange kept open, suppression happens before the connection check."""
        bridge = SocketIOChatBridge(
            websocket_url="wss://test.example.com",
            websocket_path="/socket.io",
            conversation_id="conv-123",
            exchange_id="exch-456",
            headers={},
            end_exchange=False,
        )

        # Should not raise even though _client is None.
        await bridge.emit_exchange_end_event()

    def test_get_chat_bridge_propagates_end_exchange_false(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("UIPATH_URL", "https://cloud.uipath.com")
        context = MockRuntimeContext(end_exchange=False)

        bridge = cast(SocketIOChatBridge, get_chat_bridge(cast(Any, context)))

        assert bridge.end_exchange is False

    def test_get_chat_bridge_defaults_end_exchange_true(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("UIPATH_URL", "https://cloud.uipath.com")
        context = MockRuntimeContext()

        bridge = cast(SocketIOChatBridge, get_chat_bridge(cast(Any, context)))

        assert bridge.end_exchange is True


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
    """Tests for emit_interrupt_event — registers expected tool_call_ids."""

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

    @pytest.mark.anyio
    async def test_emit_interrupt_event_does_not_emit_websocket_event(self) -> None:
        """emit_interrupt_event does not emit any websocket event."""
        bridge = self._make_bridge()

        emitted_events: list[Any] = []

        async def capture_emit(event: Any) -> None:
            emitted_events.append(event)

        bridge.emit_message_event = capture_emit  # type: ignore[assignment]

        trigger = UiPathResumeTrigger(
            api_resume=UiPathApiTrigger(
                request={
                    "tool_call_id": "tc-42",
                    "tool_name": "my_tool",
                    "input": {"key": "value"},
                }
            )
        )

        await bridge.emit_interrupt_event(trigger)

        assert len(emitted_events) == 0

    @pytest.mark.anyio
    async def test_emit_interrupt_event_registers_tool_call_id(self) -> None:
        """emit_interrupt_event adds the tool_call_id to the expected queue."""
        bridge = self._make_bridge()

        trigger = UiPathResumeTrigger(
            api_resume=UiPathApiTrigger(
                request={"tool_call_id": "tc-42", "tool_name": "my_tool"}
            )
        )

        await bridge.emit_interrupt_event(trigger)

        assert list(bridge._expected_tool_call_ids) == ["tc-42"]

    @pytest.mark.anyio
    async def test_emit_interrupt_event_skips_without_tool_call_id(self) -> None:
        """emit_interrupt_event does not register if tool_call_id is missing."""
        bridge = self._make_bridge()

        trigger = UiPathResumeTrigger(
            api_resume=UiPathApiTrigger(
                request={"tool_name": "my_tool"}
            )
        )

        await bridge.emit_interrupt_event(trigger)

        assert len(bridge._expected_tool_call_ids) == 0

    @pytest.mark.anyio
    async def test_emit_interrupt_event_registers_multiple_in_order(self) -> None:
        """Multiple emit_interrupt_event calls register IDs in FIFO order."""
        bridge = self._make_bridge()

        for tc_id in ["tc-1", "tc-2", "tc-3"]:
            trigger = UiPathResumeTrigger(
                api_resume=UiPathApiTrigger(
                    request={"tool_call_id": tc_id}
                )
            )
            await bridge.emit_interrupt_event(trigger)

        assert list(bridge._expected_tool_call_ids) == ["tc-1", "tc-2", "tc-3"]


class TestEmitExecutingToolCall:
    """Tests for emit_executing_tool_call_event (post-confirmation executingToolCall emission)."""

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

    @pytest.mark.anyio
    async def test_emits_executing_tool_call_event(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Should emit executingToolCall with tool_call_id and input."""
        monkeypatch.setenv("CAS_WEBSOCKET_DISABLED", "true")
        bridge = self._make_bridge()
        await bridge.connect()

        emitted_events: list[Any] = []
        original_emit = bridge.emit_message_event

        async def capture_emit(event: Any) -> None:
            emitted_events.append(event)
            await original_emit(event)

        bridge.emit_message_event = capture_emit  # type: ignore[assignment]

        await bridge.emit_executing_tool_call_event(
            tool_call_id="tc-42",
            tool_input={"key": "value"},
        )

        assert len(emitted_events) == 1
        event = emitted_events[0]
        assert event.message_id == "msg-100"
        assert event.tool_call is not None
        assert event.tool_call.tool_call_id == "tc-42"
        assert event.tool_call.executing is not None
        assert event.tool_call.executing.input == {"key": "value"}

    @pytest.mark.anyio
    async def test_no_message_id_does_not_emit(self) -> None:
        """Should not emit if no current message ID is set."""
        bridge = SocketIOChatBridge(
            websocket_url="wss://test.example.com",
            websocket_path="/socket.io",
            conversation_id="conv-123",
            exchange_id="exch-456",
            headers={},
        )
        # _current_message_id is not set

        emitted_events: list[Any] = []

        async def capture_emit(event: Any) -> None:
            emitted_events.append(event)

        bridge.emit_message_event = capture_emit  # type: ignore[assignment]

        await bridge.emit_executing_tool_call_event(tool_call_id="tc-42")

        assert len(emitted_events) == 0

    @pytest.mark.anyio
    async def test_none_input_emits_with_none(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Should emit with None input when no input provided."""
        monkeypatch.setenv("CAS_WEBSOCKET_DISABLED", "true")
        bridge = self._make_bridge()
        await bridge.connect()

        emitted_events: list[Any] = []
        original_emit = bridge.emit_message_event

        async def capture_emit(event: Any) -> None:
            emitted_events.append(event)
            await original_emit(event)

        bridge.emit_message_event = capture_emit  # type: ignore[assignment]

        await bridge.emit_executing_tool_call_event(tool_call_id="tc-42")

        assert len(emitted_events) == 1
        assert emitted_events[0].tool_call.executing.input is None


class TestWaitForResumeEndToolCall:
    """Tests for wait_for_resume unblocking on endToolCall events."""

    def _make_bridge(self) -> SocketIOChatBridge:
        return SocketIOChatBridge(
            websocket_url="wss://test.example.com",
            websocket_path="/socket.io",
            conversation_id="conv-123",
            exchange_id="exch-456",
            headers={},
        )

    def _make_end_event(self, tool_call_id: str, output: Any = None) -> dict[str, Any]:
        return {
            "conversationId": "conv-123",
            "exchange": {
                "exchangeId": "exch-456",
                "message": {
                    "messageId": "msg-200",
                    "toolCall": {
                        "toolCallId": tool_call_id,
                        "endToolCall": {
                            "output": output or {"result": "ok"},
                            "isError": False,
                        },
                    },
                },
            },
        }

    def _make_confirm_event(self, tool_call_id: str) -> dict[str, Any]:
        return {
            "conversationId": "conv-123",
            "exchange": {
                "exchangeId": "exch-456",
                "message": {
                    "messageId": "msg-200",
                    "toolCall": {
                        "toolCallId": tool_call_id,
                        "confirmToolCall": {
                            "approved": True,
                            "input": {"edited": "data"},
                        },
                    },
                },
            },
        }

    async def _register(self, bridge: SocketIOChatBridge, tool_call_id: str) -> None:
        """Register an expected tool_call_id via emit_interrupt_event."""
        trigger = UiPathResumeTrigger(
            api_resume=UiPathApiTrigger(request={"tool_call_id": tool_call_id})
        )
        await bridge.emit_interrupt_event(trigger)

    @pytest.mark.anyio
    async def test_end_tool_call_unblocks_wait_for_resume(self) -> None:
        """Receiving an endToolCall event unblocks wait_for_resume and returns parsed payload."""
        bridge = self._make_bridge()
        await self._register(bridge, "tc-99")

        async def simulate_end_event() -> None:
            await asyncio.sleep(0.05)
            await bridge._handle_conversation_event(self._make_end_event("tc-99"), "sid-1")

        task = asyncio.create_task(simulate_end_event())
        result = await bridge.wait_for_resume()
        await task

        assert result["output"] == {"result": "ok"}
        assert result["is_error"] is False
        assert result["tool_call_id"] == "tc-99"

    @pytest.mark.anyio
    async def test_confirm_tool_call_unblocks_wait_for_resume(self) -> None:
        """Receiving a confirmToolCall event also unblocks wait_for_resume."""
        bridge = self._make_bridge()
        await self._register(bridge, "tc-99")

        async def simulate_confirm_event() -> None:
            await asyncio.sleep(0.05)
            await bridge._handle_conversation_event(self._make_confirm_event("tc-99"), "sid-1")

        task = asyncio.create_task(simulate_confirm_event())
        result = await bridge.wait_for_resume()
        await task

        assert result["approved"] is True
        assert result["input"] == {"edited": "data"}
        assert result["tool_call_id"] == "tc-99"

    @pytest.mark.anyio
    async def test_early_end_tool_call_is_not_lost(self) -> None:
        """An endToolCall that arrives before wait_for_resume is called must not be lost."""
        bridge = self._make_bridge()
        await self._register(bridge, "tc-100")

        # Response arrives BEFORE wait_for_resume is called
        await bridge._handle_conversation_event(
            self._make_end_event("tc-100", output={"early": True}), "sid-1"
        )

        result = await bridge.wait_for_resume()

        assert result["output"] == {"early": True}
        assert result["is_error"] is False
        assert result["tool_call_id"] == "tc-100"

    @pytest.mark.anyio
    async def test_concurrent_tool_calls_all_early(self) -> None:
        """Multiple endToolCall responses arriving before any wait_for_resume are all preserved."""
        bridge = self._make_bridge()

        # Runtime registers 3 expected tool calls
        for tc_id in ["tc-1", "tc-2", "tc-3"]:
            await self._register(bridge, tc_id)

        # All 3 responses arrive before any wait_for_resume call
        for tc_id in ["tc-1", "tc-2", "tc-3"]:
            await bridge._handle_conversation_event(
                self._make_end_event(tc_id, output={"id": tc_id}), "sid-1"
            )

        # Each wait_for_resume returns the correct result matched by tool_call_id
        for tc_id in ["tc-1", "tc-2", "tc-3"]:
            result = await bridge.wait_for_resume()
            assert result["tool_call_id"] == tc_id
            assert result["output"] == {"id": tc_id}

        # All storage is empty after consumption
        assert len(bridge._tool_resume_results) == 0
        assert len(bridge._tool_resume_pending) == 0

    @pytest.mark.anyio
    async def test_concurrent_tool_calls_out_of_order(self) -> None:
        """Responses arriving in reverse order are matched to the correct wait_for_resume call."""
        bridge = self._make_bridge()

        # Runtime registers in order: tc-A, tc-B, tc-C
        for tc_id in ["tc-A", "tc-B", "tc-C"]:
            await self._register(bridge, tc_id)

        # Responses arrive in reverse order: tc-C, tc-B, tc-A
        for tc_id in ["tc-C", "tc-B", "tc-A"]:
            await bridge._handle_conversation_event(
                self._make_end_event(tc_id, output={"id": tc_id}), "sid-1"
            )

        # wait_for_resume consumes in registration order, each gets correct result
        result_a = await bridge.wait_for_resume()
        assert result_a["tool_call_id"] == "tc-A"

        result_b = await bridge.wait_for_resume()
        assert result_b["tool_call_id"] == "tc-B"

        result_c = await bridge.wait_for_resume()
        assert result_c["tool_call_id"] == "tc-C"

    @pytest.mark.anyio
    async def test_concurrent_mixed_early_and_late(self) -> None:
        """Mix of early arrivals and late arrivals are all matched correctly."""
        bridge = self._make_bridge()

        # Register 3 expected tool calls
        for tc_id in ["tc-1", "tc-2", "tc-3"]:
            await self._register(bridge, tc_id)

        # tc-1 arrives early (before any wait_for_resume)
        await bridge._handle_conversation_event(
            self._make_end_event("tc-1", output={"id": "tc-1"}), "sid-1"
        )

        # First wait_for_resume finds tc-1 already in results
        result_1 = await bridge.wait_for_resume()
        assert result_1["tool_call_id"] == "tc-1"

        # Second wait_for_resume blocks — tc-2 arrives while waiting
        async def send_tc2() -> None:
            await asyncio.sleep(0.05)
            await bridge._handle_conversation_event(
                self._make_end_event("tc-2", output={"id": "tc-2"}), "sid-1"
            )

        task = asyncio.create_task(send_tc2())
        result_2 = await bridge.wait_for_resume()
        await task
        assert result_2["tool_call_id"] == "tc-2"

        # tc-3 arrives early before third wait_for_resume
        await bridge._handle_conversation_event(
            self._make_end_event("tc-3", output={"id": "tc-3"}), "sid-1"
        )
        result_3 = await bridge.wait_for_resume()
        assert result_3["tool_call_id"] == "tc-3"

    @pytest.mark.anyio
    async def test_confirm_then_end_same_tool_call(self) -> None:
        """Tool with requireConversationalConfirmation: confirm and end are handled sequentially."""
        bridge = self._make_bridge()

        # Runtime registers the same tool_call_id twice (once for confirm, once for end)
        await self._register(bridge, "tc-42")
        await self._register(bridge, "tc-42")

        # Confirm arrives
        await bridge._handle_conversation_event(
            self._make_confirm_event("tc-42"), "sid-1"
        )

        # First wait_for_resume gets the confirm
        result_confirm = await bridge.wait_for_resume()
        assert result_confirm["approved"] is True
        assert result_confirm["tool_call_id"] == "tc-42"

        # End arrives after confirm was consumed
        async def send_end() -> None:
            await asyncio.sleep(0.05)
            await bridge._handle_conversation_event(
                self._make_end_event("tc-42", output={"done": True}), "sid-1"
            )

        task = asyncio.create_task(send_end())
        result_end = await bridge.wait_for_resume()
        await task
        assert result_end["output"] == {"done": True}
        assert result_end["tool_call_id"] == "tc-42"
