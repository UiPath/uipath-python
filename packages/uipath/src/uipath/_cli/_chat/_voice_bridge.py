"""Voice tool-call session — persistent socket.io connection to CAS."""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Awaitable, Callable
from enum import Enum
from typing import Any
from urllib.parse import urlparse

from pydantic import ValidationError

from uipath.core.chat import (
    UiPathVoiceToolCallMessage,
    UiPathVoiceToolCallRequest,
    UiPathVoiceToolCallResult,
)
from uipath.runtime.context import UiPathRuntimeContext

logger = logging.getLogger(__name__)


_ATTEMPT_CAS_SOCKET_CONNECTION_TIMEOUT_SECONDS = 15.0
_INFLIGHT_TOOL_DRAIN_AFTER_AGENT_END_TIMEOUT_SECONDS = 30.0


class VoiceToolCallSessionError(RuntimeError):
    pass


class VoiceSessionEndReason(str, Enum):
    COMPLETED = "completed"
    DISCONNECTED = "disconnected"
    READY_EMIT_FAILED = "ready_emit_failed"


class VoiceEvent(str, Enum):
    """CAS voice-session protocol events (excludes socket.io lifecycle)."""

    TOOL_CALL = "voice_tool_call"  # received
    SESSION_ENDED = "voice_session_ended"  # received
    TOOLS_READY = "voice_tools_ready"  # sent
    TOOL_RESULT = "voice_tool_result"  # sent


ToolHandler = Callable[
    [UiPathVoiceToolCallRequest], Awaitable[UiPathVoiceToolCallResult]
]


class VoiceToolCallSession:
    """Socket.io session with CAS for tool-call traffic.

    Receives `voice_tool_call` batches, emits one `voice_tool_result` per
    `callId`, exits on `voice_session_ended` or disconnect. CAS pulls
    agent config from Orchestrator directly; this session carries only
    tool calls.
    """

    def __init__(
        self,
        url: str,
        socketio_path: str,
        headers: dict[str, str],
        tool_handler: ToolHandler,
    ) -> None:
        self._url = url
        self._socketio_path = socketio_path
        self._headers = headers
        self._tool_handler = tool_handler
        self._client: Any = None
        self._done = asyncio.Event()
        self._in_flight: set[asyncio.Task[None]] = set()
        self._end_reason: VoiceSessionEndReason | None = None

    async def run(self) -> VoiceSessionEndReason:
        """Connect, dispatch tool calls until session ends, then disconnect.

        Raises:
            VoiceToolCallSessionError: If connecting to CAS fails.
        """
        from socketio import AsyncClient  # type: ignore[import-untyped]

        self._client = AsyncClient(logger=False, engineio_logger=False)
        self._client.on("connect", self._handle_connect)
        self._client.on("disconnect", self._handle_disconnect)
        self._client.on(VoiceEvent.TOOL_CALL, self._handle_tool_call)
        self._client.on(VoiceEvent.SESSION_ENDED, self._handle_session_ended)

        try:
            await asyncio.wait_for(
                self._client.connect(
                    url=self._url,
                    socketio_path=self._socketio_path,
                    headers=self._headers,
                    transports=["websocket"],
                ),
                timeout=_ATTEMPT_CAS_SOCKET_CONNECTION_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            await self._safe_disconnect("after connect-failure")
            raise VoiceToolCallSessionError(
                f"Failed to connect to CAS voice endpoint: {exc}"
            ) from exc

        try:
            await self._done.wait()
            await self._drain_in_flight()
        finally:
            await self._safe_disconnect("on shutdown")

        return self._end_reason or VoiceSessionEndReason.DISCONNECTED

    async def _safe_disconnect(self, when: str) -> None:
        try:
            await self._client.disconnect()
        except Exception as exc:
            logger.debug("[Voice] disconnect %s raised: %s", when, exc)

    def _end_session(self, reason: VoiceSessionEndReason) -> None:
        # First writer wins: a late disconnect must not overwrite COMPLETED.
        if self._end_reason is None:
            self._end_reason = reason
        self._done.set()

    async def _drain_in_flight(self) -> None:
        """Wait for in-flight tool tasks to finish, capped by the drain timeout."""
        if not self._in_flight:
            return
        logger.info(
            "[Voice] Session ended with %d in-flight tool task(s); draining (max %.0fs)",
            len(self._in_flight),
            _INFLIGHT_TOOL_DRAIN_AFTER_AGENT_END_TIMEOUT_SECONDS,
        )
        try:
            await asyncio.wait_for(
                asyncio.gather(*self._in_flight, return_exceptions=True),
                timeout=_INFLIGHT_TOOL_DRAIN_AFTER_AGENT_END_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            unfinished = sum(1 for t in self._in_flight if not t.done())
            logger.warning(
                "[Voice] %d tool task(s) did not complete within %.0fs of session end",
                unfinished,
                _INFLIGHT_TOOL_DRAIN_AFTER_AGENT_END_TIMEOUT_SECONDS,
            )

    async def _handle_connect(self) -> None:
        logger.info("[Voice] Socket.io connected to CAS")
        try:
            await self._client.emit(VoiceEvent.TOOLS_READY, {})
        except Exception as exc:
            # CAS gates tool dispatch on this event; without it the session is dead.
            logger.warning("[Voice] emit voice_tools_ready failed: %s", exc)
            self._end_session(VoiceSessionEndReason.READY_EMIT_FAILED)

    async def _handle_disconnect(self) -> None:
        logger.info("[Voice] Socket.io disconnected from CAS")
        self._end_session(VoiceSessionEndReason.DISCONNECTED)

    async def _handle_tool_call(self, data: dict[str, Any], *_: Any) -> None:
        """Spawn a task per call and return — the reader must stay free for `voice_session_ended`."""
        if self._done.is_set():
            return

        try:
            message = UiPathVoiceToolCallMessage.model_validate(data)
        except ValidationError as exc:
            logger.warning("[Voice] invalid voice_tool_call payload: %s", exc)
            return

        for call in message.calls:
            task = asyncio.create_task(self._execute_tool_call(call))
            self._in_flight.add(task)
            task.add_done_callback(self._in_flight.discard)

    async def _execute_tool_call(self, call: UiPathVoiceToolCallRequest) -> None:
        """Run one tool call and emit its `voice_tool_result`."""
        logger.info(
            "[Voice] voice_tool_call dispatched: %s (%s) args=%s",
            call.tool_name,
            call.call_id,
            call.args,
        )
        try:
            tool_result = await self._tool_handler(call)
        except Exception as exc:
            logger.exception("[Voice] Tool call execution failed: %s", call.tool_name)
            tool_result = UiPathVoiceToolCallResult(result=str(exc), is_error=True)

        try:
            await self._client.emit(
                VoiceEvent.TOOL_RESULT,
                {"callId": call.call_id, **tool_result.model_dump(by_alias=True)},
            )
        except Exception as exc:
            logger.debug(
                "[Voice] emit voice_tool_result failed for %s: %s", call.call_id, exc
            )
            return
        logger.info(
            "[Voice] voice_tool_result sent: %s (isError=%s)",
            call.call_id,
            tool_result.is_error,
        )

    async def _handle_session_ended(self, _data: Any, *_: Any) -> None:
        logger.info("[Voice] voice_session_ended received")
        self._end_session(VoiceSessionEndReason.COMPLETED)


def get_voice_bridge(
    context: UiPathRuntimeContext,
    tool_handler: ToolHandler,
) -> VoiceToolCallSession:
    """Factory for a CAS voice tool-call session.

    Raises:
        RuntimeError: If UIPATH_URL is not set or invalid.
    """
    assert context.conversation_id is not None, "conversation_id must be set in context"

    if cas_host := os.environ.get("CAS_WEBSOCKET_HOST"):
        url = f"ws://{cas_host}?conversationId={context.conversation_id}"
        socketio_path = "/socket.io"
        logger.warning(
            f"CAS_WEBSOCKET_HOST is set. Using websocket_url '{url}{socketio_path}'."
        )
    else:
        base_url = os.environ.get("UIPATH_URL")
        if not base_url:
            raise RuntimeError(
                "UIPATH_URL environment variable required for conversational mode"
            )
        parsed = urlparse(base_url)
        if not parsed.netloc:
            raise RuntimeError(f"Invalid UIPATH_URL format: {base_url}")
        url = f"wss://{parsed.netloc}?conversationId={context.conversation_id}"
        socketio_path = "autopilotforeveryone_/websocket_/socket.io"

    headers = {
        "Authorization": f"Bearer {os.environ.get('UIPATH_ACCESS_TOKEN', '')}",
        "X-UiPath-Internal-TenantId": context.tenant_id
        or os.environ.get("UIPATH_TENANT_ID", ""),
        "X-UiPath-Internal-AccountId": context.org_id
        or os.environ.get("UIPATH_ORGANIZATION_ID", ""),
        "X-UiPath-ConversationId": context.conversation_id,
    }

    return VoiceToolCallSession(
        url=url,
        socketio_path=socketio_path,
        headers=headers,
        tool_handler=tool_handler,
    )
