"""Tests for VoiceToolCallSession and get_voice_bridge."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from uipath._cli._chat._voice_bridge import (
    VoiceSessionEndReason,
    VoiceToolCallSession,
    get_voice_bridge,
)
from uipath.core.chat import (
    UiPathVoiceToolCallRequest,
    UiPathVoiceToolCallResult,
)


def _make_session(tool_handler: Any = None) -> VoiceToolCallSession:
    session = VoiceToolCallSession(
        url="wss://example/test",
        socketio_path="/socket.io",
        headers={},
        tool_handler=tool_handler or AsyncMock(),
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

    async def test_disconnect_sets_disconnected(self) -> None:
        session = _make_session()
        await session._handle_disconnect()
        assert session._end_reason == VoiceSessionEndReason.DISCONNECTED


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


class TestGetVoiceBridge:
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

        assert bridge._headers["X-UiPath-Internal-TenantId"] == "env-tenant"
        assert bridge._headers["X-UiPath-Internal-AccountId"] == "env-org"
