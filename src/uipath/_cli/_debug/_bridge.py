import asyncio
import json
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from pysignalr.client import SignalRClient

from uipath._cli._runtime._contracts import UiPathRuntimeContext


class IDebugBridge(ABC):
    """Abstract interface for debug communication.

    Implementations: SignalR, Console, WebSocket, etc.
    """

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to debugger."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to debugger."""
        pass

    @abstractmethod
    async def emit_execution_started(self, execution_id: str, **kwargs) -> None:
        """Notify debugger that execution started."""
        pass

    @abstractmethod
    async def emit_breakpoint_hit(
        self,
        execution_id: str,
        location: str,
        state: Dict[str, Any],
        resume_trigger: Any,
    ) -> None:
        """Notify debugger that a breakpoint was hit."""
        pass

    @abstractmethod
    async def emit_execution_completed(
        self,
        execution_id: str,
        status: str,
    ) -> None:
        """Notify debugger that execution completed."""
        pass

    @abstractmethod
    async def emit_execution_error(
        self,
        execution_id: str,
        error: str,
    ) -> None:
        """Notify debugger that an error occurred."""
        pass

    @abstractmethod
    async def wait_for_resume(self) -> Any:
        """Wait for resume command from debugger."""
        pass


class ConsoleDebugBridge(IDebugBridge):
    """Console-based debug bridge for local development.

    User presses Enter to continue.
    """

    async def connect(self) -> None:
        """Console is always "connected"."""
        self._connected = True
        print("\n" + "=" * 60)
        print(" Console Debugger Started")
        print("=" * 60)
        print("Commands:")
        print("  - Press ENTER to continue")
        print("=" * 60 + "\n")

    async def disconnect(self) -> None:
        """Cleanup."""
        self._connected = False
        print("\n" + "=" * 60)
        print(" Console Debugger Stopped")
        print("=" * 60 + "\n")

    async def emit_execution_started(self, execution_id: str, **kwargs) -> None:
        """Print execution started."""
        print(f"\n  Execution Started: {execution_id}")

    async def emit_breakpoint_hit(
        self,
        execution_id: str,
        location: str,
        state: Dict[str, Any],
        resume_trigger: Any,
    ) -> None:
        """Print breakpoint info and wait for user input."""
        print("\n" + "=" * 60)
        print(" BREAKPOINT HIT")
        print("=" * 60)
        print(f"Location: {location}")
        print(f"Execution: {execution_id}")
        print("\nState:")
        print(json.dumps(state, indent=2, default=str))
        print("=" * 60)

    async def emit_execution_completed(
        self,
        execution_id: str,
        status: str,
    ) -> None:
        """Print completion."""
        print(f"\n Execution Completed: {execution_id} - Status: {status}")

    async def emit_execution_error(
        self,
        execution_id: str,
        error: str,
    ) -> None:
        """Print error."""
        print(f"\n Execution Error: {execution_id}")
        print(f"Error: {error}")

    async def wait_for_resume(self) -> Any:
        """Wait for user to press Enter or type commands.

        Runs in executor to avoid blocking async loop.
        """
        print("\n Press ENTER to continue (or type command)...")

        # Run input() in executor to not block async loop
        loop = asyncio.get_running_loop()
        user_input = await loop.run_in_executor(None, input, "> ")

        return user_input


class SignalRDebugBridge(IDebugBridge):
    """SignalR-based debug bridge for remote debugging.

    Communicates with a SignalR hub server.
    """

    def __init__(
        self,
        hub_url: str,
        access_token: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ):
        self.hub_url = hub_url
        self.access_token = access_token
        self.headers = headers or {}
        self._client: Optional[SignalRClient] = None
        self._connected_event = asyncio.Event()
        self._resume_event: Optional[asyncio.Event] = None
        self._resume_data: Any = None

    async def connect(self) -> None:
        """Establish SignalR connection."""
        all_headers = {**self.headers}
        if self.access_token:
            all_headers["Authorization"] = f"Bearer {self.access_token}"

        self._client = SignalRClient(self.hub_url, headers=all_headers)

        # Register event handlers
        self._client.on("ResumeExecution", self._handle_resume)
        self._client.on_open(self._handle_open)
        self._client.on_close(self._handle_close)
        self._client.on_error(self._handle_error)

        # Start connection in background
        asyncio.create_task(self._client.run())

        # Wait for connection to establish
        await asyncio.wait_for(self._connected_event.wait(), timeout=30.0)

    async def disconnect(self) -> None:
        """Close SignalR connection."""
        if self._client and hasattr(self._client, "_transport"):
            transport = self._client._transport
            if transport and hasattr(transport, "_ws") and transport._ws:
                try:
                    await transport._ws.close()
                except Exception as e:
                    print(f"Error closing SignalR WebSocket: {e}")

    async def emit_execution_started(self, execution_id: str, **kwargs) -> None:
        """Send execution started event."""
        await self._send("OnExecutionStarted", {"executionId": execution_id, **kwargs})

    async def emit_breakpoint_hit(
        self,
        execution_id: str,
        location: str,
        state: Dict[str, Any],
        resume_trigger: Any,
    ) -> None:
        """Send breakpoint hit event."""
        await self._send(
            "OnBreakpointHit",
            {
                "executionId": execution_id,
                "location": location,
                "state": state,
                "resumeTrigger": resume_trigger,
            },
        )

    async def emit_execution_completed(
        self,
        execution_id: str,
        status: str,
    ) -> None:
        """Send execution completed event."""
        await self._send(
            "OnExecutionCompleted",
            {
                "executionId": execution_id,
                "status": status,
            },
        )

    async def emit_execution_error(
        self,
        execution_id: str,
        error: str,
    ) -> None:
        """Send execution error event."""
        await self._send(
            "OnExecutionError",
            {
                "executionId": execution_id,
                "error": error,
            },
        )

    async def wait_for_resume(self) -> Any:
        """Wait for resume command from server."""
        self._resume_event = asyncio.Event()
        await self._resume_event.wait()
        return self._resume_data

    async def _send(self, method: str, data: Dict[str, Any]) -> None:
        """Send message to SignalR hub."""
        if not self._client:
            raise RuntimeError("SignalR client not connected")

        await self._client.send(method=method, arguments=[data])

    async def _handle_resume(self, args: list[Any]) -> None:
        """Handle resume command from SignalR server."""
        if self._resume_event and len(args) > 0:
            self._resume_data = args[0]
            self._resume_event.set()

    async def _handle_open(self) -> None:
        """Handle SignalR connection open."""
        print("SignalR connection established")
        self._connected_event.set()

    async def _handle_close(self) -> None:
        """Handle SignalR connection close."""
        print("SignalR connection closed")
        self._connected_event.clear()

    async def _handle_error(self, error: Any) -> None:
        """Handle SignalR error."""
        print(f"SignalR error: {error}")


def get_remote_debug_bridge(context: UiPathRuntimeContext) -> IDebugBridge:
    """Factory to get SignalR debug bridge for remote debugging."""
    uipath_url = os.environ.get("UIPATH_URL")
    if not uipath_url or not context.job_id:
        raise ValueError(
            "UIPATH_URL and UIPATH_JOB_KEY are required for remote debugging"
        )
    if not context.trace_context:
        raise ValueError("trace_context is required for remote debugging")

    signalr_url = uipath_url + "/agenthub_/wsstunnel?jobId=" + context.job_id
    return SignalRDebugBridge(
        hub_url=signalr_url,
        access_token=os.environ.get("UIPATH_ACCESS_TOKEN"),
        headers={
            "X-UiPath-Internal-TenantId": context.trace_context.tenant_id or "",
            "X-UiPath-Internal-AccountId": context.trace_context.org_id or "",
            "X-UiPath-FolderKey": context.trace_context.folder_key or "",
        },
    )


def get_debug_bridge(context: UiPathRuntimeContext) -> IDebugBridge:
    """Factory to get appropriate debug bridge based on context.

    Args:
        context: The runtime context containing debug configuration.

    Returns:
        An instance of IDebugBridge suitable for the context.
    """
    if context.job_id:
        return get_remote_debug_bridge(context)
    else:
        return ConsoleDebugBridge()
