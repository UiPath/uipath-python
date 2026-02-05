"""Chat bridge implementations for conversational agents."""

import asyncio
import json
import logging
import os
import uuid
from typing import Any
from urllib.parse import urlparse

from uipath.core.chat import (
    UiPathConversationEvent,
    UiPathConversationExchangeEndEvent,
    UiPathConversationExchangeEvent,
    UiPathConversationGenericInterruptStart,
    UiPathConversationInterruptEvent,
    UiPathConversationMessageEvent,
)
from uipath.runtime import UiPathRuntimeResult
from uipath.runtime.chat import UiPathChatProtocol
from uipath.runtime.context import UiPathRuntimeContext

logger = logging.getLogger(__name__)


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
    ):
        """Initialize the WebSocket chat bridge.

        Args:
            websocket_url: The WebSocket server URL to connect to
            conversation_id: The conversation ID for this session
            exchange_id: The exchange ID for this session
            headers: HTTP headers to send during connection
            auth: Optional authentication data to send during connection
        """
        self.websocket_url = websocket_url
        self.websocket_path = websocket_path
        self.conversation_id = conversation_id
        self.exchange_id = exchange_id
        self.auth = auth
        self.headers = headers
        self._client: Any | None = None
        self._connected_event = asyncio.Event()

        # Interrupt handling state
        self._interrupt_id: str | None = None
        self._lg_interrupt_id: str | None = None
        self._interrupt_type: str | None = None
        self._interrupt_response_event = asyncio.Event()
        self._interrupt_resume_data: dict[str, Any] = {}
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

        Raises:
           RuntimeError: If client is not connected
        """
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

    async def emit_interrupt_event(self, runtime_result: UiPathRuntimeResult):
        if self._client is None:
            raise RuntimeError("WebSocket client not connected. Call connect() first.")

        if not self._connected_event.is_set() and not self._websocket_disabled:
            raise RuntimeError("WebSocket client not in connected state")

        try:
            interrupt_map = runtime_result.output
            if not isinstance(interrupt_map, dict) or not interrupt_map:
                logger.warning("No interrupts in runtime result output")
                return

            # Extract first interrupt (single interrupt support for v1)
            lg_interrupt_id, interrupt_data = next(iter(interrupt_map.items()))

            self._interrupt_id = str(uuid.uuid4())
            self._lg_interrupt_id = lg_interrupt_id
            self._interrupt_type = interrupt_data.get("type", "generic")

            if not self._current_message_id:
                logger.warning("No current message ID set for interrupt event")
                return

            interrupt_event = UiPathConversationEvent(
                conversation_id=self.conversation_id,
                exchange=UiPathConversationExchangeEvent(
                    exchange_id=self.exchange_id,
                    message=UiPathConversationMessageEvent(
                        message_id=self._current_message_id,
                        interrupt=UiPathConversationInterruptEvent(
                            interrupt_id=self._interrupt_id,
                            start=UiPathConversationGenericInterruptStart(
                                type=self._interrupt_type,
                                value=interrupt_data.get("value", {}),
                            ),
                        ),
                    ),
                ),
            )
            event_data = interrupt_event.model_dump(
                mode="json", exclude_none=True, by_alias=True
            )
            if self._websocket_disabled:
                logger.info(
                    f"SocketIOChatBridge is in debug mode. Not sending event: {json.dumps(event_data)}"
                )
            else:
                await self._client.emit("ConversationEvent", event_data)
        except Exception as e:
            logger.warning(f"Error sending interrupt event: {e}")

    async def wait_for_resume(self) -> dict[str, Any]:
        """Wait for the interrupt_end event to be received.

        Returns:
            Resume data with interrupt metadata for the runtime to dispatch
            transformation based on interrupt type.
        """
        if self._websocket_disabled:
            logger.warning(
                "SocketIOChatBridge is in debug mode. Returning empty resume data."
            )
            return {}

        # Clear any previous state and wait for the interrupt response
        self._interrupt_response_event.clear()
        self._interrupt_resume_data = {}

        logger.info(f"Waiting for interrupt response for interrupt_id: {self._interrupt_id}")
        await self._interrupt_response_event.wait()

        resume_data = self._interrupt_resume_data
        logger.info(f"Received interrupt response: {resume_data}")

        # Clear state after use
        self._interrupt_response_event.clear()
        self._interrupt_resume_data = {}

        # Include interrupt metadata so the runtime can dispatch correctly
        return {
            "lg_interrupt_id": self._lg_interrupt_id,
            "interrupt_type": self._interrupt_type,
            "response": resume_data,
        }

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
        """Handle received ConversationEvent events."""
        if error_event := event.get("conversationError"):
            logger.error(f"Conversation error: {json.dumps(error_event)}")

        # Extract interrupt end event via chained gets
        interrupt = event.get("exchange", {}).get("message", {}).get("interrupt", {})
        end_interrupt = interrupt.get("endInterrupt")
        if not end_interrupt:
            return

        interrupt_id = interrupt.get("interruptId")
        logger.info(f"Received interrupt end event for interrupt_id: {interrupt_id}")

        if interrupt_id == self._interrupt_id:
            self._interrupt_resume_data = end_interrupt.get("value", {})
            self._interrupt_response_event.set()

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
        "X-UiPath-Internal-TenantId": f"{context.tenant_id}"
        or os.environ.get("UIPATH_TENANT_ID", ""),
        "X-UiPath-Internal-AccountId": f"{context.org_id}"
        or os.environ.get("UIPATH_ORGANIZATION_ID", ""),
        "X-UiPath-ConversationId": context.conversation_id,
    }

    return SocketIOChatBridge(
        websocket_url=websocket_url,
        websocket_path=websocket_path,
        conversation_id=context.conversation_id,
        exchange_id=context.exchange_id,
        headers=headers,
    )


__all__ = ["get_chat_bridge"]
