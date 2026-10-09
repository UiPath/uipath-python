"""Tests for VoiceToolCallSession and get_voice_bridge."""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from uipath._cli._chat import _voice_bridge as voice_bridge
from uipath._cli._chat._voice_bridge import (
    VoiceSessionEndReason,
    VoiceToolCallSession,
    get_voice_bridge,
)
from uipath.core.chat import (
    UiPathVoiceToolCallRequest,
    UiPathVoiceToolCallResult,
    UiPathVoiceToolDescriptor,
)
from uipath.platform.constants import (
    HEADER_INTERNAL_ACCOUNT_ID,
    HEADER_INTERNAL_TENANT_ID,
)


def _make_session(
    tool_handler: Any = None, tools: list[UiPathVoiceToolDescriptor] | None = None
) -> VoiceToolCallSession:
    session = VoiceToolCallSession(
        url="wss://example/test",
        socketio_path="/socket.io",
        headers={},
        tool_handler=tool_handler or AsyncMock(),
        tools=tools or [],
    )
    session._client = MagicMock()
    session._client.emit = AsyncMock()
    return session


class TestEndSession:
    def test_first_writer_wins(self) -> None:
        """A late DISCONNECTED must not overwrite COMPLETED."""
        session = _make_session()
        session._end_session(VoiceSessionEndReason.COMPLETED)
        session._end_session(VoiceSessionEndReason.DISCONNECTED)
        assert session._end_reason == VoiceSessionEndReason.COMPLETED
        assert session._done.is_set()

    async def test_session_ended_sets_completed(self) -> None:
        session = _make_session()
        await session._handle_session_ended(None)
        assert session._end_reason == VoiceSessionEndReason.COMPLETED

    async def test_session_ended_preserves_payload_opaquely(self) -> None:
        session = _make_session()
        payload = {
            "callContext": {
                "type": "phone",
                "id": "CA123",
                "conversationId": "conv-1",
            },
            "endedBy": "agent",
            "callEnded": False,
            "reason": "agent_completed",
            "someFutureKey": {"nested": True},
        }

        await session._handle_session_ended(payload)

        assert session.end_detail == payload
        assert session._end_reason == VoiceSessionEndReason.COMPLETED
        returned_detail = session.end_detail
        returned_detail["reason"] = "mutated"
        returned_detail["callContext"]["id"] = "CA999"
        payload["endedBy"] = "system"
        assert session.end_detail["reason"] == "agent_completed"
        assert session.end_detail["callContext"]["id"] == "CA123"
        assert session.end_detail["endedBy"] == "agent"

    async def test_session_ended_preserves_output_envelope(self) -> None:
        """The voice outputs envelope must reach the job runtime untouched."""
        session = _make_session()
        envelope = {
            "fields": {"caller_name": "Ada", "callback_requested": None},
            "status": "extracted",
            "extracted": True,
        }
        payload = {
            "callEnded": True,
            "endedBy": "agent",
            "reason": "agent_completed",
            "endToolCalled": True,
            "output": envelope,
        }

        await session._handle_session_ended(payload)

        assert session.end_detail["output"] == envelope
        assert session.end_detail["endToolCalled"] is True

    async def test_session_ended_non_dict_payload_is_empty_detail(self) -> None:
        session = _make_session()
        await session._handle_session_ended("not-a-dict")
        assert session.end_detail == {}
        assert session._end_reason == VoiceSessionEndReason.COMPLETED

    async def test_late_session_ended_does_not_overwrite_terminal_state(self) -> None:
        session = _make_session()
        await session._handle_session_ended({"endedBy": "agent", "callEnded": False})

        await session._handle_session_ended({"endedBy": "system", "callEnded": True})

        assert session.end_detail == {"endedBy": "agent", "callEnded": False}
        assert session._end_reason == VoiceSessionEndReason.COMPLETED

    async def test_disconnect_sets_disconnected(self) -> None:
        session = _make_session()
        await session._handle_disconnect()
        assert session._end_reason == VoiceSessionEndReason.DISCONNECTED


class TestToolsReady:
    async def test_announces_registered_tools(self) -> None:
        session = _make_session(
            tools=[
                UiPathVoiceToolDescriptor(name="Lookup", resource_name="Lookup"),
                UiPathVoiceToolDescriptor(
                    name="mcp-crm-tool-get_account",
                    resource_name="CRM",
                    mcp_tool_name="get_account",
                ),
            ]
        )

        await session._handle_connect()

        session._client.emit.assert_awaited_once_with(
            "voice_tools_ready",
            {
                "tools": [
                    {"name": "Lookup", "resourceName": "Lookup"},
                    {
                        "name": "mcp-crm-tool-get_account",
                        "resourceName": "CRM",
                        "mcpToolName": "get_account",
                    },
                ]
            },
        )

    async def test_announces_empty_list_without_tools(self) -> None:
        session = _make_session()

        await session._handle_connect()

        session._client.emit.assert_awaited_once_with(
            "voice_tools_ready", {"tools": []}
        )

    async def test_emit_failure_ends_session(self) -> None:
        session = _make_session()
        session._client.emit.side_effect = RuntimeError("socket closed")

        await session._handle_connect()

        assert session._end_reason == VoiceSessionEndReason.READY_EMIT_FAILED


class TestHandleToolCall:
    async def test_dispatches_handler_and_emits_result(self) -> None:
        handler = AsyncMock(
            return_value=UiPathVoiceToolCallResult(result="ok", is_error=False)
        )
        session = _make_session(handler)

        await session._handle_tool_call(
            {"calls": [{"callId": "c1", "toolName": "weather", "args": {"city": "SF"}}]}
        )
        # Drain the spawned task.
        for task in list(session._in_flight):
            await task

        handler.assert_awaited_once()
        assert handler.await_args is not None
        call_arg = handler.await_args.args[0]
        assert isinstance(call_arg, UiPathVoiceToolCallRequest)
        assert call_arg.call_id == "c1"
        assert call_arg.tool_name == "weather"

        session._client.emit.assert_awaited_once_with(
            "voice_tool_result",
            {"callId": "c1", "result": "ok", "isError": False},
        )

    async def test_invalid_payload_is_skipped(self) -> None:
        handler = AsyncMock()
        session = _make_session(handler)

        await session._handle_tool_call({"calls": []})  # min_length=1 violation

        handler.assert_not_awaited()
        session._client.emit.assert_not_awaited()

    async def test_noop_after_session_ended(self) -> None:
        handler = AsyncMock()
        session = _make_session(handler)
        session._done.set()

        await session._handle_tool_call(
            {"calls": [{"callId": "c1", "toolName": "x", "args": {}}]}
        )

        handler.assert_not_awaited()
        assert not session._in_flight

    async def test_handler_exception_emits_error_result(self) -> None:
        handler = AsyncMock(side_effect=RuntimeError("boom"))
        session = _make_session(handler)

        await session._handle_tool_call(
            {"calls": [{"callId": "c1", "toolName": "x", "args": {}}]}
        )
        for task in list(session._in_flight):
            await task

        session._client.emit.assert_awaited_once_with(
            "voice_tool_result",
            {"callId": "c1", "result": "boom", "isError": True},
        )


class TestDrainInFlight:
    async def test_cancels_tasks_still_running_at_timeout(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            voice_bridge, "_INFLIGHT_TOOL_DRAIN_AFTER_AGENT_END_TIMEOUT_SECONDS", 0.01
        )
        never_finishes = asyncio.Event()

        async def handler(_: Any) -> UiPathVoiceToolCallResult:
            await never_finishes.wait()
            return UiPathVoiceToolCallResult(result="late", is_error=False)

        session = _make_session(handler)
        await session._handle_tool_call(
            {"calls": [{"callId": "c1", "toolName": "slow", "args": {}}]}
        )
        tasks = list(session._in_flight)

        await session._drain_in_flight()

        # The call is over before run() returns, so callers can release what it used.
        assert all(task.cancelled() for task in tasks)
        session._client.emit.assert_not_awaited()


class TestGetVoiceBridge:
    def test_passes_tools_to_session(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("UIPATH_URL", "https://cloud.uipath.com")
        ctx = MagicMock(conversation_id="conv-1", tenant_id="t", org_id="o")
        tools = [UiPathVoiceToolDescriptor(name="Lookup", resource_name="Lookup")]

        bridge = get_voice_bridge(ctx, AsyncMock(), tools=tools)

        assert bridge._tools == tools

    def test_raises_when_uipath_url_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("UIPATH_URL", raising=False)
        monkeypatch.delenv("CAS_WEBSOCKET_HOST", raising=False)
        ctx = MagicMock(conversation_id="conv-1", tenant_id="t", org_id="o")

        with pytest.raises(RuntimeError, match="UIPATH_URL"):
            get_voice_bridge(ctx, AsyncMock())

    def test_headers_fall_back_to_env_when_context_ids_are_none(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Regression: f"{None}" is truthy ("None"), so the `or` fallback was dead."""
        monkeypatch.setenv("UIPATH_URL", "https://cloud.uipath.com")
        monkeypatch.setenv("UIPATH_TENANT_ID", "env-tenant")
        monkeypatch.setenv("UIPATH_ORGANIZATION_ID", "env-org")
        ctx = MagicMock(conversation_id="conv-1", tenant_id=None, org_id=None)

        bridge = get_voice_bridge(ctx, AsyncMock())

        assert bridge._headers[HEADER_INTERNAL_TENANT_ID] == "env-tenant"
        assert bridge._headers[HEADER_INTERNAL_ACCOUNT_ID] == "env-org"

    def test_includes_conversational_user_id_header_when_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Conversation owner id (from FpsProperties) is sent on the handshake for CAS to validate."""
        monkeypatch.setenv("UIPATH_URL", "https://cloud.uipath.com")
        ctx = MagicMock(
            conversation_id="conv-1",
            tenant_id="t",
            org_id="o",
            conversational_user_id="owner-guid",
        )

        bridge = get_voice_bridge(ctx, AsyncMock())

        assert bridge._headers["X-UiPath-Internal-ConversationalUserId"] == "owner-guid"

    def test_omits_conversational_user_id_header_when_none(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No header is sent when the runtime has no owner id (backward compatible)."""
        monkeypatch.setenv("UIPATH_URL", "https://cloud.uipath.com")
        ctx = MagicMock(
            conversation_id="conv-1",
            tenant_id="t",
            org_id="o",
            conversational_user_id=None,
        )

        bridge = get_voice_bridge(ctx, AsyncMock())

        assert "X-UiPath-Internal-ConversationalUserId" not in bridge._headers
