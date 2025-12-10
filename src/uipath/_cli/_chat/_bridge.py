"""Chat bridge implementations for conversational agents."""

import asyncio
import logging
import os
from typing import Any
from urllib.parse import urlparse

import socketio  # type: ignore[import-untyped]
from socketio import AsyncClient
from uipath.core.chat import (
    UiPathConversationEvent,
    UiPathConversationExchangeEndEvent,
    UiPathConversationExchangeEvent,
)
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
        self._client: AsyncClient | None = None
        self._connected_event = asyncio.Event()

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
        self._client = socketio.AsyncClient(
            logger=logger,
            engineio_logger=logger,
        )

        # Register connection event handlers
        self._client.on("connect", self._handle_connect)
        self._client.on("disconnect", self._handle_disconnect)
        self._client.on("connect_error", self._handle_connect_error)

        # Clear connection event
        self._connected_event.clear()

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

            # Wait for connection confirmation
            await asyncio.wait_for(self._connected_event.wait(), timeout=timeout)

            logger.info("WebSocket connection established successfully")

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

        # Send exchange end event using stored IDs
        if self._client and self._connected_event.is_set():
            try:
                end_event = UiPathConversationEvent(
                    conversation_id=self.conversation_id,
                    exchange=UiPathConversationExchangeEvent(
                        exchange_id=self.exchange_id,
                        end=UiPathConversationExchangeEndEvent(),
                    ),
                )
                event_data = end_event.model_dump(
                    mode="json", exclude_none=True, by_alias=True
                )
                await self._client.emit("ConversationEvent", event_data)
                logger.info("Exchange end event sent")
            except Exception as e:
                logger.warning(f"Error sending exchange end event: {e}")

        try:
            logger.info("Disconnecting from WebSocket server")
            await self._client.disconnect()
            logger.info("WebSocket disconnected successfully")
        except Exception as e:
            logger.error(f"Error during WebSocket disconnect: {e}")
        finally:
            await self._cleanup_client()

    async def emit_message_event(self, message_event: Any) -> None:
        """Wrap and send a message event to the WebSocket server.

        Args:
            message_event: UiPathConversationMessageEvent to wrap and send

        Raises:
            RuntimeError: If client is not connected
        """
        if self._client is None:
            raise RuntimeError("WebSocket client not connected. Call connect() first.")

        if not self._connected_event.is_set():
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

            logger.debug("Sending conversation event to WebSocket")
            await self._client.emit("ConversationEvent", event_data)
            logger.debug("Conversation event sent successfully")

        except Exception as e:
            logger.error(f"Error sending conversation event to WebSocket: {e}")
            raise RuntimeError(f"Failed to send conversation event: {e}") from e

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
