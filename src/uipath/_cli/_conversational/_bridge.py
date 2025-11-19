import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Optional

import socketio
from rich.console import Console

from uipath._cli._runtime._contracts import UiPathRuntimeContext
from uipath._events._events import UiPathAgentMessageEvent
from uipath.agent.conversation import (
    UiPathConversationEvent,
    UiPathConversationExchangeEvent,
    UiPathConversationExchangeEndEvent,
)

logger = logging.getLogger(__name__)


class UiPathConversationBridge(ABC):
    """Abstract interface for conversational agent communication.

    Implementations: Console, WebSocket.
    """

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection."""
        pass

    @abstractmethod
    async def disconnect(self, conversation_id: str, exchange_id: str) -> None:
        """Close connection. Sends exchange end event before disconnecting."""
        pass

    @abstractmethod
    async def emit_message(self, message_event: UiPathAgentMessageEvent) -> None:
        """Send message to WebSocket or console."""
        pass

class WebSocketConversationBridge(UiPathConversationBridge):
    """WebSocket bridge for sending messages to CAS"""

    def __init__(
        self,
        uipath_url: str,
        access_token: Optional[str] = None,
        tenant_id: Optional[str] = None,
        account_id: Optional[str] = None,
    ):
        self.uipath_url = uipath_url
        self.access_token = access_token
        self.client: Optional[socketio.AsyncClient] = None
        self.tenant_id = tenant_id
        self.account_id = account_id
        self._session_started = asyncio.Event()
        self._conversation_id: Optional[str] = "b2c6e7df-41cd-4144-b637-96db39b90e2b"

    async def connect(self) -> None:
        """Connect to the websocket."""
        try:
            logger.warning("Creating socketio client...")
            self.client = socketio.AsyncClient(logger=True, engineio_logger=True)

            # Register event handlers
            @self.client.on("connect")
            async def on_connect():
                logger.warning("✓ Socket.IO connected successfully")

            @self.client.on("connect_error")
            async def on_connect_error(data):
                logger.error(f"✗ Socket.IO connection error: {data}")

            @self.client.on("disconnect")
            async def on_disconnect():
                logger.warning("Socket.IO disconnected")

            @self.client.on("message")
            async def on_message(data):
                logger.warning(f"Received message from server: {data}")
                # Check if this is a sessionStarted event
                if isinstance(data, dict):
                    if "sessionStarted" in data:
                        self._conversation_id = data.get("conversationId")
                        logger.info(f"✓ Session started for conversation: {self._conversation_id}")
                        self._session_started.set()

            @self.client.on("*")
            async def catch_all(event, data):
                logger.warning(f"Received event '{event}': {data}")

            await asyncio.wait_for(
                self.client.connect(
                    #self.uipath_url,
                    "http://localhost:8080?conversationId=13789ac9-3b08-45c5-a010-78ab3816facc",
                    socketio_path="/socket.io",
                    transports=["websocket"],
                    headers={
                        "X-UiPath-Internal-TenantId": self.tenant_id,
                        "X-UiPath-Internal-AccountId": self.account_id,
                        "Authorization": "",
                        "X-UiPath-ConversationId": "13789ac9-3b08-45c5-a010-78ab3816facc"
                    },
                ),
                timeout=30.0,
            )
            logger.info("✓ WebSocket connection established")

        except asyncio.TimeoutError as e:
            logger.error(f"✗ Connection timeout: {e}")
            raise
        except Exception as e:
            logger.error(f"✗ Connection failed: {e}", exc_info=True)
            raise

    async def disconnect(self, conversation_id: str, exchange_id: str) -> None:
        """Close connection to WebSocket. Sends exchange end event before disconnecting."""
        # Send exchange end event before disconnecting
        if self.client and self.client.connected:
            try:
                end_event = UiPathConversationEvent(
                    conversation_id=conversation_id,
                    exchange=UiPathConversationExchangeEvent(
                        exchange_id=exchange_id,
                        end=UiPathConversationExchangeEndEvent(),
                    ),
                )
                event_data = end_event.model_dump(mode="json", exclude_none=True, by_alias=True)
                await self.client.emit("ConversationEvent", event_data)
                logger.info("Exchange end event sent")
            except Exception as e:
                logger.warning(f"Error sending exchange end event: {e}")

        if self.client and self.client.connected:
            try:
                await asyncio.wait_for(self.client.disconnect(), timeout=30.0)
                logger.info("WebSocket connection closed")
            except Exception as e:
                logger.warning(f"Error disconnecting WebSocket: {e}")

    async def emit_message(self, message_event: UiPathAgentMessageEvent) -> None:
        """Send LLM message to CAS via WebSocket."""
        print("📤 emit_message() called")

        if not self.client or not self.client.connected:
            print("❌ WebSocket client not connected!")
            logger.error("WebSocket client not connected, cannot emit message")
            return

        try:
            print("📨 Sending message through WebSocket")
            logger.warning("Sending message through WebSocket")

            # Payload is UiPathConversationEvent (converted by LangGraph runtime)
            conversation_event = message_event.payload

            # Serialize to JSON for transmission with aliases (conversationId, exchangeId, etc.)
            event_data = conversation_event.model_dump(mode="json", exclude_none=True, by_alias=True)

            # Print the event to console for debugging
            import json
            print("=" * 80)
            print("📦 Event being sent:")
            print(json.dumps(event_data, indent=2))
            print("=" * 80)

            # Emit the event through the WebSocket using ConversationEvent
            await self.client.emit("ConversationEvent", event_data)
            print(f"✅ Message emitted successfully")
            logger.debug(f"Emitted message event: {event_data}")

        except Exception as e:
            print(f"❌ Failed to emit: {e}")
            logger.error(f"Failed to emit message through WebSocket: {e}", exc_info=True)


class ConsoleConversationBridge(UiPathConversationBridge):
    """Console bridge for displaying LLM messages locally."""

    def __init__(self):
        """Initialize console conversation bridge."""
        self.console = Console()

    async def connect(self) -> None:
        """Display conversation mode header."""
        self.console.print()
        self.console.print("[bold cyan]─" * 40)
        self.console.print("[bold cyan]Conversational Agent Mode")
        self.console.print("[bold cyan]─" * 40)
        self.console.print()

    async def disconnect(self, conversation_id: str, exchange_id: str) -> None:
        """Display completion message."""
        self.console.print()
        self.console.print("[dim]─" * 40)
        self.console.print("[green]Conversation completed")
        self.console.print("[dim]─" * 40)

    async def emit_message(self, message_event: UiPathAgentMessageEvent) -> None:
        """Display LLM message in console as JSON."""
        import json

        # Payload is UiPathConversationEvent (converted by LangGraph runtime)
        conversation_event = message_event.payload

        # Serialize to JSON for display
        try:
            event_data = conversation_event.model_dump(mode="json", exclude_none=True)
            json_str = json.dumps(event_data, indent=2)
            self.console.print(f"[blue]Event:[/blue]")
            self.console.print(json_str)
            self.console.print()  # Empty line for separation
        except Exception as e:
            logger.error(f"Failed to serialize conversation event: {e}")
            # Fallback to string representation
            self.console.print(f"[red]Error serializing event:[/red] {e}")
            self.console.print(str(conversation_event))


def get_remote_conversation_bridge(context: UiPathRuntimeContext) -> UiPathConversationBridge:
    """Factory to get WebSocket conversation bridge for cloud runs."""
    import os

    logger.warning("Requesting WebSocket conversation bridge")
    logger.warning(f"UIPATH_URL: {os.environ.get('UIPATH_URL')}")
    #uipath_url = os.environ.get("UIPATH_URL")
    #if not uipath_url or not context.job_id:
     #   raise ValueError(
      #      "UIPATH_URL and UIPATH_JOB_KEY are required for web socket conversation bridge"
      #  )
    #if not context.trace_context:
    #    raise ValueError("trace_context is required for remote conversation bridge")

    return WebSocketConversationBridge(
        uipath_url="http://localhost:8080",
        access_token=os.environ.get("UIPATH_ACCESS_TOKEN"),
        tenant_id="6961A069-3392-40CA-BF5D-276F4E54C8FF",
        account_id="B7006B1C-11C3-4A80-802E-FEE0EBF9C360"
        #tenant_id=context.trace_context.tenant_id or "",
        #account_id=context.trace_context.org_id or "",
    )


def get_conversation_bridge(context: UiPathRuntimeContext) -> UiPathConversationBridge:
    """Factory to get appropriate conversation bridge based on context.

    Args:
        context: The runtime context containing configuration.

    Returns:
        An instance of UiPathConversationBridge suitable for the context.
    """
    if context.job_id:
        return get_remote_conversation_bridge(context)
    else:
        return ConsoleConversationBridge()

