"""Chat bridge implementations for conversational agents."""

import asyncio
import json
import logging
import os
from collections import deque
from typing import Any
from urllib.parse import urlparse

from uipath.core.chat import (
    UiPathConversationErrorEvent,
    UiPathConversationErrorStartEvent,
    UiPathConversationEvent,
    UiPathConversationExchangeEndEvent,
    UiPathConversationExchangeEvent,
    UiPathConversationExecutingToolCallEvent,
    UiPathConversationMessageEvent,
    UiPathConversationToolCallConfirmationEvent,
    UiPathConversationToolCallEndEvent,
    UiPathConversationToolCallEvent,
)
from uipath.core.triggers import UiPathResumeTrigger
from uipath.runtime.chat import UiPathChatProtocol
from uipath.runtime.context import UiPathRuntimeContext

logger = logging.getLogger(__name__)

# Type for tool call resume values (confirmToolCall or endToolCall payloads)
ToolResumeValue = (
    UiPathConversationToolCallConfirmationEvent | UiPathConversationToolCallEndEvent
)

# Wrapper that pairs a resume value with its tool_call_id for keyed matching
ToolResumeItem = dict[str, Any]  # {"tool_call_id": str, "value": ToolResumeValue}


class CASErrorId:
    """Error IDs for the Conversational Agent Service (CAS), matching the Temporal backend."""

    LICENSING = "AGENT_LICENSING_CONSUMPTION_VALIDATION_FAILED"
    INCOMPLETE_RESPONSE = "AGENT_RESPONSE_IS_INCOMPLETE"
    MAX_STEPS_REACHED = "AGENT_MAXIMUM_SEQUENTIAL_STEPS_REACHED"
    INVALID_INPUT = "AGENT_INVALID_INPUT"
    DEFAULT_ERROR = "AGENT_RUNTIME_ERROR"


# User-facing messages for each CAS error ID, matching the Temporal backend.
_CAS_ERROR_MESSAGES: dict[str, str] = {
    CASErrorId.LICENSING: "Your action could not be completed. You've used all your units for this period. Please contact your administrator to add more units or wait until your allowance replenishes, then try again.",
    CASErrorId.INCOMPLETE_RESPONSE: "Could not obtain a full response from the model through streamed completion call.",
    CASErrorId.MAX_STEPS_REACHED: "Maximum number of sequential steps reached. You may send a new message to tell the agent to continue.",
    CASErrorId.DEFAULT_ERROR: "An unexpected error has occurred.",
}

# Error code suffix mappings to CAS error IDs.
_CAS_ERROR_ID_MAP: dict[str, str] = {
    "LICENSE_NOT_AVAILABLE": CASErrorId.LICENSING,
    "UNSUCCESSFUL_STOP_REASON": CASErrorId.INCOMPLETE_RESPONSE,
    "TERMINATION_MAX_ITERATIONS": CASErrorId.MAX_STEPS_REACHED,
    "INVALID_INPUT_FILE_EXTENSION": CASErrorId.INVALID_INPUT,
    "MISSING_INPUT_FILE": CASErrorId.INVALID_INPUT,
    "INPUT_INVALID_JSON": CASErrorId.INVALID_INPUT,
}


def _extract_error_info(error: Exception) -> tuple[str, str]:
    """Extract an error code and a user-facing message from an exception.

    For UiPathBaseRuntimeError (structured errors), extracts code and builds
    a message from title + detail. For other exceptions, returns defaults.
    """
    from uipath.runtime.errors import UiPathBaseRuntimeError

    if isinstance(error, UiPathBaseRuntimeError):
        info = error.error_info
        code = info.code or CASErrorId.DEFAULT_ERROR
        title = info.title or ""
        detail = info.detail.split("\n")[0] if info.detail else ""
        if title and detail:
            message = f"{title}. {detail}"
        else:
            message = title or detail or _CAS_ERROR_MESSAGES[CASErrorId.DEFAULT_ERROR]
        return code, message

    return CASErrorId.DEFAULT_ERROR, _CAS_ERROR_MESSAGES[CASErrorId.DEFAULT_ERROR]


def _resolve_cas_error(error: Exception) -> tuple[str, str]:
    """Map an exception to a CAS error ID and user-facing message.

    Extracts the error code from the exception, then checks the code suffix
    against known mappings. For recognized errors, uses a hardcoded message
    matching the Temporal backend. For unrecognized errors, passes through
    the extracted message.
    """
    error_code, error_message = _extract_error_info(error)
    suffix = error_code.rsplit(".", 1)[-1] if error_code else ""
    cas_error_id = _CAS_ERROR_ID_MAP.get(suffix, CASErrorId.DEFAULT_ERROR)
    cas_message = _CAS_ERROR_MESSAGES.get(cas_error_id) or error_message
    return cas_error_id, cas_message


class SocketIOChatBridge:
    """WebSocket-based chat bridge for streaming conversational events to CAS.

    Implements UiPathChatBridgeProtocol using python-socketio library.
    """

    def __init__(
        self,
        websocket_url: str,
        websocket_path: str,
        conversation_id: str,
        exchange_id: str,
        headers: dict[str, str],
        auth: dict[str, Any] | None = None,
        end_exchange: bool = True,
    ):
        """Initialize the WebSocket chat bridge.

        Args:
            websocket_url: The WebSocket server URL to connect to
            conversation_id: The conversation ID for this session
            exchange_id: The exchange ID for this session
            headers: HTTP headers to send during connection
            auth: Optional authentication data to send during connection
            end_exchange: Whether to send the exchange-end event to CAS on
                completion.
        """
        self.websocket_url = websocket_url
        self.websocket_path = websocket_path
        self.conversation_id = conversation_id
        self.exchange_id = exchange_id
        self.auth = auth
        self.headers = headers
        self.end_exchange = end_exchange
        self._client: Any | None = None
        self._connected_event = asyncio.Event()

        # --- Tool call resume state ---
        # When the LLM invokes multiple tools in one turn, the client can send
        # back confirmToolCall / endToolCall responses concurrently and in any
        # order.  Three data structures coordinate matching each response to the
        # correct wait_for_resume() call:
        #
        # 1. _expected_tool_call_ids (deque):
        #    Ordered queue of tool_call_ids populated by emit_interrupt_event()
        #    (called by the runtime BEFORE each wait_for_resume()).  Tells
        #    wait_for_resume() WHICH tool_call_id it should consume next.
        #
        # 2. _tool_resume_results (dict):
        #    Responses that arrived BEFORE wait_for_resume() was called for that
        #    tool_call_id.  When wait_for_resume() runs, it checks here first
        #    and returns immediately if a match exists — no blocking needed.
        #
        # 3. _tool_resume_pending (dict of Futures):
        #    Created by wait_for_resume() when the response hasn't arrived yet.
        #    When the response later arrives in _handle_conversation_event, the
        #    Future is resolved and wait_for_resume() unblocks.
        self._tool_resume_results: dict[str, ToolResumeItem] = {}
        self._tool_resume_pending: dict[str, asyncio.Future[ToolResumeItem]] = {}
        self._expected_tool_call_ids: deque[str] = deque()
        self._current_message_id: str | None = None

        # Set CAS_WEBSOCKET_DISABLED when using the debugger to prevent websocket errors from
        # interrupting the debugging session. Events will be logged instead of being sent.
        self._websocket_disabled = os.environ.get("CAS_WEBSOCKET_DISABLED") == "true"

    async def connect(self, timeout: float = 10.0) -> None:
        """Establish WebSocket connection to the server.

        Args:
            timeout: Connection timeout in seconds (default: 10.0)

        Raises:
            RuntimeError: If connection fails or times out

        Example:
            ```python
            manager = WebSocketManager("http://localhost:3000")
            await manager.connect()
            ```
        """
        if self._client is not None:
            logger.warning("WebSocket client already connected")
            return

        # Create new SocketIO client
        # Lazy import to avoid dependency if not used, improve startup time
        from socketio import AsyncClient  # type: ignore[import-untyped]

        self._client = AsyncClient(
            logger=logger,
            engineio_logger=logger,
        )

        # Register connection event handlers
        self._client.on("connect", self._handle_connect)
        self._client.on("disconnect", self._handle_disconnect)
        self._client.on("connect_error", self._handle_connect_error)
        self._client.on("ConversationEvent", self._handle_conversation_event)

        self._connected_event.clear()

        if self._websocket_disabled:
            logger.warning(
                "SocketIOChatBridge is in debug mode. Not connecting websocket."
            )
        else:
            try:
                # Attempt to connect with timeout
                await asyncio.wait_for(
                    self._client.connect(
                        url=self.websocket_url,
                        socketio_path=self.websocket_path,
                        headers=self.headers,
                        auth=self.auth,
                        transports=["websocket"],
                    ),
                    timeout=timeout,
                )

                await asyncio.wait_for(self._connected_event.wait(), timeout=timeout)

            except asyncio.TimeoutError as e:
                error_message = (
                    f"Failed to connect to WebSocket server within {timeout}s timeout"
                )
                logger.error(error_message)
                await self._cleanup_client()
                raise RuntimeError(error_message) from e

            except Exception as e:
                error_message = f"Failed to connect to WebSocket server: {e}"
                logger.error(error_message)
                await self._cleanup_client()
                raise RuntimeError(error_message) from e

    async def disconnect(self) -> None:
        """Close the WebSocket connection gracefully.

        Sends an exchange end event before disconnecting to signal that the
        exchange is complete. Uses stored conversation/exchange IDs.
        """
        if self._client is None:
            logger.warning("WebSocket client not connected")
            return

        try:
            # Wait for last event to be sent (usually endExchange). Without this, it seems that the disconnect races
            # with the send and sometimes the last event isn't sent. Since the wait happens after the agent has
            # completed it doesn't add latency for the user, but it does create a larger window where the job isn't
            # suspended or terminated yet and a new input message is received from the user. CAS expects coded
            # conversational agent jobs to suspend at the end of an exchange, and for low code agent jobs to terminate
            # at the end of an exchange. CAS will resume or re-start jobs when a new user input message is received. To
            # handle the race condition should an input be received before the job is actually suspended or terminated,
            # CAS waits for running jobs to suspend or terminate before resuming or starting a new job. Note that this
            # window exists even without this additional wait, but would usually be much smaller so is less of a
            # concern.
            await asyncio.sleep(1)
            await self._client.disconnect()
        except Exception as e:
            logger.error(f"Error during WebSocket disconnect: {e}")
        finally:
            await self._cleanup_client()

    async def emit_message_event(
        self, message_event: UiPathConversationMessageEvent
    ) -> None:
        """Wrap and send a message event to the WebSocket server.

        Args:
            message_event: UiPathConversationMessageEvent to wrap and send

        Raises:
            RuntimeError: If client is not connected
        """
        if self._client is None:
            raise RuntimeError("WebSocket client not connected. Call connect() first.")

        if not self._connected_event.is_set() and not self._websocket_disabled:
            raise RuntimeError("WebSocket client not in connected state")

        try:
            # Wrap message event with conversation/exchange IDs
            wrapped_event = UiPathConversationEvent(
                conversation_id=self.conversation_id,
                exchange=UiPathConversationExchangeEvent(
                    exchange_id=self.exchange_id,
                    message=message_event,
                ),
            )

            event_data = wrapped_event.model_dump(
                mode="json", exclude_none=True, by_alias=True
            )

            if self._websocket_disabled:
                logger.info(
                    f"SocketIOChatBridge is in debug mode. Not sending event: {json.dumps(event_data)}"
                )
            else:
                await self._client.emit("ConversationEvent", event_data)

            # Store the current message ID, used for emitting interrupt events.
            self._current_message_id = message_event.message_id

        except Exception as e:
            logger.error(f"Error sending conversation event to WebSocket: {e}")
            raise RuntimeError(f"Failed to send conversation event: {e}") from e

    async def emit_exchange_end_event(self) -> None:
        """Send an exchange end event.

        When end_exchange is False the exchange is left open — the event is not
        sent to CAS so a downstream consumer can continue and end it later.

        Raises:
           RuntimeError: If client is not connected
        """
        if not self.end_exchange:
            logger.info("end_exchange is False; leaving the exchange open.")
            return

        if self._client is None:
            raise RuntimeError("WebSocket client not connected. Call connect() first.")

        if not self._connected_event.is_set() and not self._websocket_disabled:
            raise RuntimeError("WebSocket client not in connected state")

        try:
            exchange_end_event = UiPathConversationEvent(
                conversation_id=self.conversation_id,
                exchange=UiPathConversationExchangeEvent(
                    exchange_id=self.exchange_id,
                    end=UiPathConversationExchangeEndEvent(),
                ),
            )

            event_data = exchange_end_event.model_dump(
                mode="json", exclude_none=True, by_alias=True
            )

            if self._websocket_disabled:
                logger.info(
                    f"SocketIOChatBridge is in debug mode. Not sending event: {json.dumps(event_data)}"
                )
            else:
                await self._client.emit("ConversationEvent", event_data)

        except Exception as e:
            logger.error(f"Error sending conversation event to WebSocket: {e}")
            raise RuntimeError(f"Failed to send conversation event: {e}") from e

    async def emit_exchange_error_event(self, error: Exception) -> None:
        """Send an exchange error event to signal an error to the UI.

        Extracts error information from the exception and maps it to
        CAS-specific error IDs and messages matching the Temporal backend
        for frontend consistency.

        Args:
            error: The exception that caused the error.
        """
        if self._client is None:
            raise RuntimeError("WebSocket client not connected. Call connect() first.")

        if not self._connected_event.is_set() and not self._websocket_disabled:
            raise RuntimeError("WebSocket client not in connected state")

        # Extract and map error to CAS-specific error ID and message.
        cas_error_id, cas_message = _resolve_cas_error(error)

        try:
            exchange_error_event = UiPathConversationEvent(
                conversation_id=self.conversation_id,
                exchange=UiPathConversationExchangeEvent(
                    exchange_id=self.exchange_id,
                    error=UiPathConversationErrorEvent(
                        error_id=cas_error_id,
                        start=UiPathConversationErrorStartEvent(
                            message=cas_message,
                        ),
                    ),
                ),
            )

            event_data = exchange_error_event.model_dump(
                mode="json", exclude_none=True, by_alias=True
            )

            if self._websocket_disabled:
                logger.info(
                    f"SocketIOChatBridge is in debug mode. Not sending event: {json.dumps(event_data)}"
                )
            else:
                await self._client.emit("ConversationEvent", event_data)

        except Exception as e:
            logger.error(f"Error sending exchange error event to WebSocket: {e}")
            raise RuntimeError(f"Failed to send exchange error event: {e}") from e

    async def emit_interrupt_event(self, resume_trigger: UiPathResumeTrigger):
        """Register the trigger's tool_call_id for the upcoming wait_for_resume().

        Does not emit any websocket event — tool confirmation and execution
        events are handled elsewhere.  The runtime calls this immediately
        before wait_for_resume() for each trigger, so we record the
        tool_call_id here so wait_for_resume() knows which response to match.
        """
        if resume_trigger.api_resume and isinstance(
            resume_trigger.api_resume.request, dict
        ):
            tool_call_id = resume_trigger.api_resume.request.get("tool_call_id")
            if tool_call_id:
                self._expected_tool_call_ids.append(tool_call_id)

    async def emit_executing_tool_call_event(
        self,
        tool_call_id: str,
        tool_input: dict[str, Any] | None = None,
    ) -> None:
        """Emit an executingToolCall event.

        Called by the runtime loop after a tool-call confirmation resumes
        to signal that the tool is about to execute with the final input.
        """
        if not self._current_message_id:
            return

        executing_event = UiPathConversationMessageEvent(
            message_id=self._current_message_id,
            tool_call=UiPathConversationToolCallEvent(
                tool_call_id=tool_call_id,
                executing=UiPathConversationExecutingToolCallEvent(
                    input=tool_input,
                ),
            ),
        )
        await self.emit_message_event(executing_event)

    async def wait_for_resume(self) -> dict[str, Any]:
        """Wait for a tool resume event (confirmToolCall or endToolCall).

        Pops the next expected tool_call_id (registered by emit_interrupt_event)
        and returns the matching response.  Two cases:

        1. Response already arrived (stored in _tool_resume_results) — return
           immediately without blocking.
        2. Response hasn't arrived yet — create a Future in _tool_resume_pending,
           block until _handle_conversation_event resolves it.

        Returns:
            The resume data dict, including ``tool_call_id``.
        """
        if not self._expected_tool_call_ids:
            raise RuntimeError(
                "wait_for_resume() called but no tool_call_id was registered "
                "by emit_interrupt_event(). This indicates a caller/protocol mismatch."
            )

        expected_id = self._expected_tool_call_ids.popleft()

        if expected_id in self._tool_resume_results:
            # Response arrived before we got here — return it immediately
            item = self._tool_resume_results.pop(expected_id)
        else:
            # Response hasn't arrived yet — wait for it
            future: asyncio.Future[ToolResumeItem] = (
                asyncio.get_running_loop().create_future()
            )
            self._tool_resume_pending[expected_id] = future
            item = await future

        value = item["value"]
        result = value.model_dump(mode="python", by_alias=False)
        result["tool_call_id"] = item["tool_call_id"]
        return result

    def _resolve_or_store_resume(
        self, tool_call_id: str, value: ToolResumeValue
    ) -> None:
        """Route an incoming confirmToolCall/endToolCall to the correct consumer.

        Called from _handle_conversation_event when a tool resume response
        arrives from the client.  Two cases:

        1. wait_for_resume() is already waiting (Future in _tool_resume_pending)
           — resolve the Future so it unblocks immediately.
        2. wait_for_resume() hasn't been called yet for this tool_call_id
           — store in _tool_resume_results so it's found instantly when
           wait_for_resume() runs later.
        """
        item: ToolResumeItem = {"tool_call_id": tool_call_id, "value": value}
        if tool_call_id in self._tool_resume_pending:
            future = self._tool_resume_pending.pop(tool_call_id)
            if not future.done():
                future.set_result(item)
            else:
                logger.warning(
                    f"Duplicate resume for tool_call_id={tool_call_id} — "
                    "future already resolved, ignoring."
                )
        else:
            if tool_call_id in self._tool_resume_results:
                logger.warning(
                    f"Duplicate resume for tool_call_id={tool_call_id} — "
                    "overwriting previously stored result."
                )
            self._tool_resume_results[tool_call_id] = item

    @property
    def is_connected(self) -> bool:
        """Check if the WebSocket is currently connected.

        Returns:
            True if connected, False otherwise
        """
        return self._client is not None and self._connected_event.is_set()

    async def _handle_connect(self) -> None:
        """Handle successful connection event."""
        logger.info("WebSocket connection established")
        self._connected_event.set()

    async def _handle_disconnect(self) -> None:
        """Handle disconnection event."""
        logger.info("WebSocket connection closed")
        self._connected_event.clear()

    async def _handle_connect_error(self, data: Any) -> None:
        """Handle connection error event."""
        logger.error(f"WebSocket connection error: {data}")

    async def _handle_conversation_event(
        self, event: dict[str, Any], _sid: str
    ) -> None:

        try:
            parsed_event = UiPathConversationEvent(**event)
            if (
                parsed_event.exchange
                and parsed_event.exchange.message
                and (tool_call := parsed_event.exchange.message.tool_call)
            ):
                if confirm := tool_call.confirm:
                    self._resolve_or_store_resume(tool_call.tool_call_id, confirm)
                elif end := tool_call.end:
                    self._resolve_or_store_resume(tool_call.tool_call_id, end)
        except Exception as e:
            logger.warning(f"Error parsing conversation event: {e}")

    async def _cleanup_client(self) -> None:
        """Clean up client resources."""
        self._connected_event.clear()
        self._client = None


def get_chat_bridge(
    context: UiPathRuntimeContext,
) -> UiPathChatProtocol:
    """Factory to get WebSocket chat bridge for conversational agents.

    Args:
        context: The runtime context containing environment configuration
        conversation_id: The conversation ID for this session
        exchange_id: The exchange ID for this session

    Returns:
        WebSocketChatBridge instance configured for CAS

    Raises:
        RuntimeError: If UIPATH_URL is not set or invalid

    Example:
        ```python
        bridge = get_chat_bridge(context, "conv-123", "exch-456")
        await bridge.connect()
        await bridge.emit_message_event(message_event)
        await bridge.disconnect(conversation_id, exchange_id)
        ```
    """
    assert context.conversation_id is not None, "conversation_id must be set in context"
    assert context.exchange_id is not None, "exchange_id must be set in context"

    # Extract host from UIPATH_URL
    base_url = os.environ.get("UIPATH_URL")
    if not base_url:
        raise RuntimeError(
            "UIPATH_URL environment variable required for conversational mode"
        )

    parsed = urlparse(base_url)
    if not parsed.netloc:
        raise RuntimeError(f"Invalid UIPATH_URL format: {base_url}")

    host = parsed.netloc

    # Construct WebSocket URL for CAS
    websocket_url = f"wss://{host}?conversationId={context.conversation_id}"
    websocket_path = "autopilotforeveryone_/websocket_/socket.io"

    if os.environ.get("CAS_WEBSOCKET_HOST"):
        websocket_url = f"ws://{os.environ.get('CAS_WEBSOCKET_HOST')}?conversationId={context.conversation_id}"
        websocket_path = "/socket.io"
        logger.warning(
            f"CAS_WEBSOCKET_HOST is set. Using websocket_url '{websocket_url}{websocket_path}'."
        )

    # Build headers from context
    headers = {
        "Authorization": f"Bearer {os.environ.get('UIPATH_ACCESS_TOKEN', '')}",
        "X-UiPath-Internal-TenantId": context.tenant_id
        or os.environ.get("UIPATH_TENANT_ID", ""),
        "X-UiPath-Internal-AccountId": context.org_id
        or os.environ.get("UIPATH_ORGANIZATION_ID", ""),
        "X-UiPath-ConversationId": context.conversation_id,
    }

    # Conversation owner id (conversationalService.conversationalUserId) that CAS forwards via
    # FpsProperties; always sent when present. It's there for RunAsMe=false, where the unattended
    # robot's token subject is the robot account rather than the conversation owner, so CAS validates
    # this presented id against conversation.user_id on the handshake instead of the token subject.
    # Sent as a header (not a query param) to keep it out of access / load-balancer logs.
    conversational_user_id = getattr(context, "conversational_user_id", None)
    if conversational_user_id:
        headers["X-UiPath-Internal-ConversationalUserId"] = conversational_user_id

    return SocketIOChatBridge(
        websocket_url=websocket_url,
        websocket_path=websocket_path,
        conversation_id=context.conversation_id,
        exchange_id=context.exchange_id,
        headers=headers,
        end_exchange=getattr(context, "end_exchange", True),
    )


__all__ = ["get_chat_bridge"]
