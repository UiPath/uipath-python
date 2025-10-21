import asyncio
import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from pysignalr.client import SignalRClient
from rich.console import Console
from rich.syntax import Syntax

from uipath._cli._runtime._contracts import (
    UiPathBreakpointResult,
    UiPathRuntimeContext,
    UiPathRuntimeResult,
    UiPathRuntimeStatus,
)
from uipath._events._events import UiPathAgentStateEvent

logger = logging.getLogger(__name__)


class UiPathDebugBridge(ABC):
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
    async def emit_state_update(self, state_event: UiPathAgentStateEvent) -> None:
        """Notify debugger of agent state update."""
        pass

    @abstractmethod
    async def emit_breakpoint_hit(
        self, breakpoint_result: UiPathBreakpointResult
    ) -> None:
        """Notify debugger that a breakpoint was hit."""
        pass

    @abstractmethod
    async def emit_execution_completed(
        self,
        runtime_result: UiPathRuntimeResult,
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


class ConsoleDebugBridge(UiPathDebugBridge):
    """Console-based debug bridge for local development."""

    def __init__(self, verbose: bool = True):
        """Initialize console debug bridge.

        Args:
            verbose: If True, show state updates. If False, only show breakpoints.
        """
        self.console = Console()
        self.verbose = verbose

    async def connect(self) -> None:
        """Connect to console debugger."""
        self.console.print()
        self.console.print("[bold cyan]─" * 40)
        self.console.print("[bold cyan]Debug Mode")
        self.console.print("[dim]Press ENTER to continue | Type 'quit' to exit")
        self.console.print("[bold cyan]─" * 40)
        self.console.print()

    async def disconnect(self) -> None:
        """Cleanup."""
        self.console.print()
        self.console.print("[dim]─" * 40)
        self.console.print("[green]Debug session completed")
        self.console.print("[dim]─" * 40)

    async def emit_execution_started(self, execution_id: str, **kwargs) -> None:
        """Print execution started."""
        self.console.print("[green]▶ START[/green] [dim]")

    async def emit_state_update(self, state_event: UiPathAgentStateEvent) -> None:
        """Print agent state update."""
        if not self.verbose:
            return

        self.console.print(f"[yellow]●[/yellow] [bold]{state_event.node_name}[/bold]")
        if state_event.payload:
            self._print_json(state_event.payload, label="State")

    async def emit_breakpoint_hit(
        self, breakpoint_result: UiPathBreakpointResult
    ) -> None:
        """Print breakpoint info."""
        self.console.print()
        self.console.print("[red]─" * 40)
        self.console.print(
            f"[red]■ BREAKPOINT[/red] [bold]{breakpoint_result.breakpoint_node}[/bold] "
            f"[dim]({breakpoint_result.breakpoint_type})"
        )

        if breakpoint_result.next_nodes:
            self.console.print(f"[dim]Next: {', '.join(breakpoint_result.next_nodes)}")

        self.console.print("[red]─" * 40)

        # Display current state
        if breakpoint_result.current_state:
            self._print_json(breakpoint_result.current_state, label="State")

    async def emit_execution_completed(
        self,
        runtime_result: "UiPathRuntimeResult",
    ) -> None:
        """Print completion."""
        self.console.print()

        status: UiPathRuntimeStatus = runtime_result.status
        if status == UiPathRuntimeStatus.SUCCESSFUL:
            color = "green"
            symbol = "●"
        elif status == UiPathRuntimeStatus.SUSPENDED:
            color = "yellow"
            symbol = "■"
        else:
            color = "blue"
            symbol = "●"

        self.console.print(f"[{color}]{symbol} END[/{color}]")
        if runtime_result.output:
            self._print_json(runtime_result.output, label="Output")

    async def emit_execution_error(
        self,
        execution_id: str,
        error: str,
    ) -> None:
        """Print error."""
        self.console.print()
        self.console.print("[red]─" * 40)
        self.console.print(f"[red]✗ Error[/red] [dim]{execution_id}")
        self.console.print("[red]─" * 40)

        # Truncate very long errors
        error_display = error
        if len(error) > 500:
            error_display = error[:500] + "\n[dim]... (truncated)"

        self.console.print(f"[white]{error_display}[/white]")
        self.console.print("[red]─" * 40)

    async def wait_for_resume(self) -> Any:
        """Wait for user to press Enter or type commands."""
        self.console.print()
        self.console.print("[cyan]> [/cyan]", end="")

        # Run input() in executor to not block async loop
        loop = asyncio.get_running_loop()
        user_input = await loop.run_in_executor(None, input)

        if user_input.strip().lower() == "quit":
            raise KeyboardInterrupt("User requested exit")

        self.console.print()
        return user_input

    def _print_json(self, data: Dict[str, Any], label: str = "Data") -> None:
        """Print JSON data in a readable format."""
        try:
            json_str = json.dumps(data, indent=2, default=str)

            # Limit output if too large
            is_truncated = False
            if len(json_str) > 2000:
                json_str = json_str[:2000] + "\n..."
                is_truncated = True

            syntax = Syntax(
                json_str,
                "json",
                theme="monokai",
                line_numbers=False,
                background_color="default",
            )

            self.console.print()
            truncated_text = " (truncated)" if is_truncated else ""
            self.console.print(f"[dim]{label}{truncated_text}:")
            self.console.print(syntax)
            self.console.print()
        except Exception:
            # Fallback to simple print
            self.console.print()
            self.console.print(f"[dim]{label}:")
            self.console.print(str(data))
            self.console.print()


class SignalRDebugBridge(UiPathDebugBridge):
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
                    logger.warning(f"Error closing SignalR WebSocket: {e}")

    async def emit_execution_started(self, execution_id: str, **kwargs) -> None:
        """Send execution started event."""
        logger.info(f"Execution started: {execution_id}")
        await self._send("OnExecutionStarted", {"executionId": execution_id, **kwargs})

    async def emit_state_update(self, state_event: UiPathAgentStateEvent) -> None:
        """Send agent state update to remote debugger."""
        logger.info(f"State update: {state_event.node_name}")
        await self._send(
            "OnStateUpdate",
            {
                "executionId": state_event.execution_id,
                "nodeName": state_event.node_name,
                "state": state_event.payload,
            },
        )

    async def emit_breakpoint_hit(
        self, breakpoint_result: UiPathBreakpointResult
    ) -> None:
        """Send breakpoint hit event."""
        logger.info(
            f"Breakpoint hit: {breakpoint_result.breakpoint_node} "
            f"({breakpoint_result.breakpoint_type})"
        )
        await self._send(
            "OnBreakpointHit",
            {
                "node": breakpoint_result.breakpoint_node,
                "type": breakpoint_result.breakpoint_type,
                "state": breakpoint_result.current_state,
                "nextNodes": breakpoint_result.next_nodes,
            },
        )

    async def emit_execution_completed(
        self,
        runtime_result: UiPathRuntimeResult,
    ) -> None:
        """Send execution completed event."""
        logger.info(f"Execution completed: {runtime_result.status}")
        await self._send(
            "OnExecutionCompleted",
            {
                "status": runtime_result.status,
                "output": runtime_result.output,
            },
        )

    async def emit_execution_error(
        self,
        execution_id: str,
        error: str,
    ) -> None:
        """Send execution error event."""
        logger.error(f"Execution error: {execution_id} - {error}")
        await self._send(
            "OnExecutionError",
            {
                "executionId": execution_id,
                "error": error,
            },
        )

    async def wait_for_resume(self) -> Any:
        """Wait for resume command from server."""
        logger.info("Waiting for resume command...")
        self._resume_event = asyncio.Event()
        await self._resume_event.wait()
        logger.info("Resume command received")
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
        logger.info("SignalR connection established")
        self._connected_event.set()

    async def _handle_close(self) -> None:
        """Handle SignalR connection close."""
        logger.info("SignalR connection closed")
        self._connected_event.clear()

    async def _handle_error(self, error: Any) -> None:
        """Handle SignalR error."""
        logger.error(f"SignalR error: {error}")


def get_remote_debug_bridge(context: UiPathRuntimeContext) -> UiPathDebugBridge:
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


def get_debug_bridge(
    context: UiPathRuntimeContext, verbose: bool = True
) -> UiPathDebugBridge:
    """Factory to get appropriate debug bridge based on context.

    Args:
        context: The runtime context containing debug configuration.
        verbose: If True, console bridge shows all state updates. If False, only breakpoints.

    Returns:
        An instance of UiPathDebugBridge suitable for the context.
    """
    if context.job_id:
        return get_remote_debug_bridge(context)
    else:
        return ConsoleDebugBridge(verbose=verbose)
