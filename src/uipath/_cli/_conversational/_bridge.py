import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Optional

import socketio
from rich.console import Console

from uipath._cli._runtime._contracts import UiPathRuntimeContext
from uipath._events._events import UiPathAgentMessageEvent

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
    async def disconnect(self) -> None:
        """Close connection."""
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

    async def connect(self) -> None:
        """Connect to the websocket."""
        self.client = socketio.AsyncClient(logger=True, engineio_logger=True)
        await asyncio.wait_for(
            self.client.connect(
                self.uipath_url,
                auth={"token": self.access_token},
                socketio_path="/autopilotforeveryone_/websocket_/socket.io",
                transports=["websocket"],
                headers={
                    "x-uipath-internal-tenantid": self.tenant_id,
                    "x-uipath-account-id": self.account_id,
                },
            ),
            timeout=30.0,
        )
        logger.info("WebSocket connection established")

    async def disconnect(self) -> None:
        """Close connection to WebSocket."""
        if self.client and self.client.connected:
            try:
                await asyncio.wait_for(self.client.disconnect(), timeout=30.0)
                logger.info("WebSocket connection closed")
            except Exception as e:
                logger.warning(f"Error disconnecting WebSocket: {e}")

    async def emit_message(self, message_event: UiPathAgentMessageEvent) -> None:
        pass


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

    async def disconnect(self) -> None:
        """Display completion message."""
        self.console.print()
        self.console.print("[dim]─" * 40)
        self.console.print("[green]Conversation completed")
        self.console.print("[dim]─" * 40)

    async def emit_message(self, message_event: UiPathAgentMessageEvent) -> None:
        """Display LLM message in console."""
        # Extract message content from the payload
        message = message_event.payload

        # Handle different message types
        if hasattr(message, "content"):
            content = message.content
        else:
            content = str(message)

        # Display the message with formatting
        if content:
            self.console.print(f"[blue]💬[/blue] {content}")


def get_remote_conversation_bridge(context: UiPathRuntimeContext) -> UiPathConversationBridge:
    """Factory to get WebSocket conversation bridge for cloud runs."""
    import os

    uipath_url = os.environ.get("UIPATH_URL")
    if not uipath_url or not context.job_id:
        raise ValueError(
            "UIPATH_URL and UIPATH_JOB_KEY are required for web socket conversation bridge"
        )
    if not context.trace_context:
        raise ValueError("trace_context is required for remote conversation bridge")

    return WebSocketConversationBridge(
        uipath_url=uipath_url,
        access_token=os.environ.get("UIPATH_ACCESS_TOKEN"),
        tenant_id=context.trace_context.tenant_id or "",
        account_id=context.trace_context.org_id or "",
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

