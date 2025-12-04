import asyncio
import json
import logging
import os
import signal
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel
from pysignalr.client import SignalRClient
from rich.console import Console
from rich.syntax import Syntax
from rich.tree import Tree
from uipath.runtime import (
    UiPathBreakpointResult,
    UiPathRuntimeContext,
    UiPathRuntimeResult,
    UiPathRuntimeStatus,
)
from uipath.runtime.debug import UiPathDebugBridgeProtocol, UiPathDebugQuitError
from uipath.runtime.events import UiPathRuntimeStateEvent
from uipath.runtime.resumable import UiPathResumeTriggerType

from uipath._cli._utils._common import serialize_object

logger = logging.getLogger(__name__)


class DebugCommand(str, Enum):
    """Available debug commands."""

    CONTINUE = "continue"
    STEP = "step"
    BREAKPOINT = "breakpoint"
    LIST_BREAKPOINTS = "list"
    CLEAR_BREAKPOINT = "clear"
    HELP = "help"
    QUIT = "quit"


class DebuggerState:
    """Maintains debugger state across execution."""

    def __init__(self):
        self.breakpoints: set[str] = set()
        self.step_mode: bool = False

    def add_breakpoint(self, node_name: str) -> None:
        """Add a breakpoint at a node."""
        self.breakpoints.add(node_name)

    def remove_breakpoint(self, node_name: str) -> None:
        """Remove a breakpoint from a node."""
        self.breakpoints.discard(node_name)

    def clear_all_breakpoints(self) -> None:
        """Clear all breakpoints."""
        self.breakpoints.clear()

    def should_break(self, node_name: str) -> bool:
        """Check if execution should break at this node."""
        if self.step_mode:
            return True
        return node_name in self.breakpoints


class ConsoleDebugBridge:
    """Console-based debug bridge for local development."""

    def __init__(self, verbose: bool = True):
        """Initialize console debug bridge.

        Args:
            verbose: If True, show state updates. If False, only show breakpoints.
        """
        self.console = Console(force_terminal=True)
        self.verbose = verbose
        self.state = DebuggerState()

        self._stdin_executor = ThreadPoolExecutor(max_workers=1)
        self._terminate_event: asyncio.Event | None = None
        self._waiting_for_resume_data = False

    async def connect(self) -> None:
        """Initialize the console debugger."""
        self._terminate_event = asyncio.Event()
        signal.signal(
            signal.SIGINT, self._handle_sigint
        )  # We need to catch CTRL+C during polling
        self.console.print()
        self._print_help()

    async def disconnect(self) -> None:
        """Clean up console debugger."""
        self.console.print()
        self.console.print("[dim]─" * 40)
        self.console.print("[green]Debug session completed")
        self.console.print("[dim]─" * 40)

    async def emit_execution_started(self, **kwargs) -> None:
        """Print execution started."""
        self.console.print("[green]▶ START[/green] [dim]")

    async def emit_state_update(self, state_event: UiPathRuntimeStateEvent) -> None:
        """Print agent state update."""
        if not self.verbose:
            return

        self.console.print(f"[yellow]●[/yellow] [bold]{state_event.node_name}[/bold]")
        if state_event.payload:
            self._print_json(state_event.payload, label="state")

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

        if breakpoint_result.current_state:
            self._print_json(breakpoint_result.current_state, label="state")

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
        output_data: dict[str, Any] | str = {}
        if runtime_result.output:
            if isinstance(runtime_result.output, BaseModel):
                output_data = runtime_result.output.model_dump()
            else:
                output_data = runtime_result.output
        self._print_json(output_data, label="output")

    async def emit_execution_suspended(
        self,
        runtime_result: UiPathRuntimeResult,
    ) -> None:
        """Print execution suspended."""
        self.console.print("[yellow]●[/yellow] [bold]<suspended>[/bold]")
        if runtime_result.trigger is None:
            return

        if runtime_result.trigger.trigger_type == UiPathResumeTriggerType.API:
            if runtime_result.output is None:
                self._print_json({}, label="output")
            elif isinstance(runtime_result.output, BaseModel):
                self._print_json(runtime_result.output.model_dump(), label="output")
            else:
                self._print_json(runtime_result.output, label="output")
            self.console.print("[dim]Please provide your input:[/dim]")

            self._waiting_for_resume_data = True
        else:
            self._print_json(
                runtime_result.trigger.model_dump() if runtime_result.trigger else {},
                label="trigger",
            )

    async def emit_execution_resumed(self, resume_data: Any) -> None:
        """Send execution resumed event."""
        self.console.print("[yellow]●[/yellow] [bold]<resumed>[/bold]")
        self._print_json(
            resume_data.model_dump()
            if resume_data and isinstance(resume_data, BaseModel)
            else resume_data or {},
            label="data",
        )

    async def emit_execution_error(
        self,
        error: str,
    ) -> None:
        """Print error."""
        self.console.print()
        self.console.print("[red]─" * 40)
        self.console.print("[red]✗ Error[/red]")
        self.console.print("[red]─" * 40)

        # Truncate very long errors
        error_display = error
        if len(error) > 500:
            error_display = error[:500] + "\n[dim]... (truncated)"

        self.console.print(f"[red]{error_display}[/red]")
        self.console.print("[red]─" * 40)

    async def wait_for_resume(self) -> Any:
        """Wait for user to press Enter or type commands."""
        while True:  # Keep looping until we get a resume command
            self.console.print()

            loop = asyncio.get_running_loop()
            future = loop.run_in_executor(
                self._stdin_executor, self._read_input_blocking
            )

            try:
                user_input = await future
            except asyncio.CancelledError:
                return {"command": DebugCommand.CONTINUE, "args": None}

            if self._waiting_for_resume_data:
                self._waiting_for_resume_data = False

                stripped_input = user_input.strip()

                # Try parse JSON, otherwise return raw string
                try:
                    return json.loads(stripped_input)
                except Exception:
                    return stripped_input

            command_result = self._parse_command(user_input.strip())

            # Handle commands that need another prompt

            if command_result["command"] in {
                DebugCommand.BREAKPOINT,
                DebugCommand.LIST_BREAKPOINTS,
                DebugCommand.CLEAR_BREAKPOINT,
                DebugCommand.HELP,
            }:
                # These commands don't resume execution, loop again
                continue

            # Commands that resume execution: CONTINUE, STEP
            self.console.print()
            return command_result

    async def wait_for_terminate(self) -> None:
        """Wait until user requests termination (Ctrl+C or 'q')."""
        assert self._terminate_event is not None, "Debugger not connected"
        await self._terminate_event.wait()

    def get_breakpoints(self) -> list[str] | Literal["*"]:
        """Get nodes to suspend execution at."""
        if self.state.step_mode:
            return "*"  # Suspend at all nodes
        return list(self.state.breakpoints)  # Only suspend at breakpoints

    def _read_input_blocking(self) -> str:
        assert self._terminate_event is not None, "Debugger not connected"
        try:
            return input("> ")
        except KeyboardInterrupt as e:
            self._terminate_event.set()
            raise UiPathDebugQuitError("User pressed Ctrl+C") from e
        except EOFError as e:
            self._terminate_event.set()
            raise UiPathDebugQuitError("STDIN closed by user") from e

    def _handle_sigint(self, signum: int, frame: Any) -> None:
        assert self._terminate_event is not None, "Debugger not connected"
        asyncio.get_running_loop().call_soon_threadsafe(self._terminate_event.set)

    def _parse_command(self, user_input: str) -> dict[str, Any]:
        """Parse user command input.

        Returns:
            Dict with 'command' and optional 'args'
        """
        assert self._terminate_event is not None, "Debugger not connected"

        if not user_input:
            return {"command": DebugCommand.CONTINUE, "args": None}

        parts = user_input.lower().split()
        cmd = parts[0]
        args = parts[1:] if len(parts) > 1 else []

        if cmd in ["c", "continue"]:
            self.state.step_mode = False
            return {"command": DebugCommand.CONTINUE, "args": None}

        elif cmd in ["s", "step"]:
            self.state.step_mode = True
            return {"command": DebugCommand.STEP, "args": None}

        elif cmd in ["b", "break", "breakpoint"]:
            if not args:
                self.console.print(
                    "[red]Error: breakpoint command requires a node name[/red]"
                )
                return {"command": DebugCommand.HELP, "args": None}
            node_name = " ".join(args)
            self.state.add_breakpoint(node_name)
            self.console.print(f"[green]✓ Breakpoint set at: {node_name}[/green]")
            return {"command": DebugCommand.BREAKPOINT, "args": {"node": node_name}}

        elif cmd in ["l", "list"]:
            self._list_breakpoints()
            return {"command": DebugCommand.LIST_BREAKPOINTS, "args": None}

        elif cmd in ["r", "remove", "delete"]:
            if not args:
                self.console.print("[yellow]Removing all breakpoints[/yellow]")
                self.state.clear_all_breakpoints()
            else:
                node_name = " ".join(args)
                self.state.remove_breakpoint(node_name)
                self.console.print(f"[green]✓ Breakpoint removed: {node_name}[/green]")
            return {
                "command": DebugCommand.CLEAR_BREAKPOINT,
                "args": {"node": " ".join(args) if args else None},
            }

        elif cmd in ["q", "quit", "exit"]:
            self._terminate_event.set()
            raise UiPathDebugQuitError("User requested exit")

        elif cmd in ["h", "help", "?"]:
            self._print_help()
            return {"command": DebugCommand.HELP, "args": None}

        else:
            self.console.print(f"[red]Unknown command: {cmd}[/red]")
            self.console.print("[dim]Type 'help' for available commands[/dim]")
            return {"command": DebugCommand.HELP, "args": None}

    def _list_breakpoints(self) -> None:
        """List all active breakpoints."""
        if not self.state.breakpoints:
            self.console.print("[dim]No breakpoints set[/dim]")
        else:
            self.console.print("[yellow]Active breakpoints:[/yellow]")
            for i, bp in enumerate(sorted(self.state.breakpoints), 1):
                self.console.print(f"  {i}. [cyan]{bp}[/cyan]")

    def _print_help(self) -> None:
        """Print available commands."""
        self.console.print("[bold cyan]Debug Mode Commands[/bold cyan]")
        self.console.print(
            "  [yellow]c, continue[/yellow]     Continue until next breakpoint"
        )
        self.console.print("  [yellow]s, step[/yellow]         Step to next node")
        self.console.print(
            "  [yellow]b  <node>[/yellow]       Set breakpoint at <node>"
        )
        self.console.print("  [yellow]l, list[/yellow]         List all breakpoints")
        self.console.print(
            "  [yellow]r  <node>[/yellow]       Remove breakpoint at <node>"
        )
        self.console.print("  [yellow]h, help[/yellow]         Show help")
        self.console.print("  [yellow]q, quit[/yellow]         Exit debugger")
        self.console.print()

    def _print_json(self, data: dict[str, Any] | str, label: str = "data") -> None:
        """Print JSON data with enhanced hierarchy."""
        try:
            # Create a tree for nested structure
            tree = Tree(f"[bold cyan]{label}[/bold cyan]")

            def process_value(
                node: Tree, value: Any, key_label: str, depth: int
            ) -> None:
                """Process a single value and add it to the tree."""
                if isinstance(value, BaseModel):
                    branch = node.add(
                        f"{key_label} [dim]({type(value).__name__})[/dim]"
                    )
                    add_to_tree(branch, value, depth + 1)
                elif isinstance(value, dict):
                    branch = node.add(f"{key_label} [dim](dict)[/dim]")
                    add_to_tree(branch, value, depth + 1)
                elif isinstance(value, list):
                    branch = node.add(
                        f"{key_label} [dim](list, {len(value)} items)[/dim]"
                    )
                    add_to_tree(branch, value, depth + 1)
                else:
                    val_str = str(value)
                    if len(val_str) > 250:
                        val_str = val_str[:250] + "..."
                    node.add(f"{key_label}: [green]{val_str}[/green]")

            def add_to_tree(node: Tree, payload: Any, depth: int = 0):
                if depth > 10:
                    node.add("[dim]...[/dim]")
                    return

                if isinstance(payload, BaseModel):
                    try:
                        payload = payload.model_dump()  # Pydantic v2
                    except AttributeError:
                        payload = payload.dict()  # Pydantic v1
                    add_to_tree(node, payload, depth)

                elif isinstance(payload, dict):
                    for key, value in payload.items():
                        process_value(node, value, f"[yellow]{key}[/yellow]", depth)

                elif isinstance(payload, list):
                    for i, item in enumerate(payload):
                        process_value(node, item, f"[cyan]#{i}[/cyan]", depth)

                else:
                    val_str = str(payload)
                    if len(val_str) > 250:
                        val_str = val_str[:250] + "..."
                    node.add(f"[green]{val_str}[/green]")

            add_to_tree(tree, data)

            self.console.print()
            self.console.print(tree)
            self.console.print()

        except Exception:
            try:
                json_str = json.dumps(data, indent=2, default=str)
                if len(json_str) > 10000:
                    json_str = json_str[:10000] + "\n..."

                syntax = Syntax(json_str, "json", theme="monokai", line_numbers=False)
                self.console.print(f"\n[dim]{label}:")
                self.console.print(syntax)
                self.console.print()
            except Exception:
                # Fallback to simple print
                self.console.print()
                self.console.print(f"[dim]{label}:")
                self.console.print(str(data))
                self.console.print()


class SignalRDebugBridge:
    """SignalR-based debug bridge for remote debugging.

    Communicates with a SignalR hub server.
    """

    def __init__(
        self,
        hub_url: str,
        access_token: str | None = None,
        headers: dict[str, str] | None = None,
    ):
        self.hub_url = hub_url
        self.access_token = access_token
        self.headers = headers or {}
        self.state = DebuggerState()
        self._client: SignalRClient | None = None
        self._connected_event = asyncio.Event()
        self._resume_event: asyncio.Event | None = None
        self._terminate_event = asyncio.Event()

    async def connect(self) -> None:
        """Establish SignalR connection."""
        all_headers = {**self.headers}
        if self.access_token:
            all_headers["Authorization"] = f"Bearer {self.access_token}"

        self._client = SignalRClient(self.hub_url, headers=all_headers)

        # Register event handlers
        self._client.on("Start", self._handle_start)
        self._client.on("Resume", self._handle_resume)
        self._client.on("Step", self._handle_step)
        self._client.on("AddBreakpoints", self._handle_add_breakpoints)
        self._client.on("RemoveBreakpoints", self._handle_remove_breakpoints)
        self._client.on("Quit", self._handle_quit)
        self._client.on_open(self._handle_open)
        self._client.on_close(self._handle_close)
        self._client.on_error(self._handle_error)

        self._run_task = asyncio.create_task(self._client.run())

        async def cleanup_run_task() -> str:
            error_message = (
                "Failed to establish WebSocket connection within 10s timeout"
            )

            if self._run_task:
                if not self._run_task.done():
                    self._run_task.cancel()
                try:
                    await self._run_task
                except asyncio.CancelledError:
                    pass  # Expected on cancel
                except Exception as task_error:
                    error_msg = str(task_error).strip()
                    error_detail = f": {error_msg}" if error_msg else ""
                    return f"{error_message}: {type(task_error).__name__}{error_detail}"

            return error_message

        try:
            # Wait for connection with timeout
            await asyncio.wait_for(self._connected_event.wait(), timeout=10.0)
        except asyncio.TimeoutError as e:
            # Clean up on timeout
            raise RuntimeError(await cleanup_run_task()) from e
        except Exception:
            # Clean up on any other error
            await cleanup_run_task()
            raise

        # Check if run_task failed
        if self._run_task.done():
            exception = self._run_task.exception()
            if exception:
                raise exception

    async def disconnect(self) -> None:
        """Close SignalR connection."""
        if not self._client:
            return

        # Cancel the run task first
        if self._run_task and not self._run_task.done():
            self._run_task.cancel()
            try:
                await self._run_task
            except (Exception, asyncio.CancelledError):
                pass

        # Try to close the client cleanly
        try:
            if hasattr(self._client, "_transport"):
                transport = self._client._transport
                if transport and hasattr(transport, "_ws") and transport._ws:
                    await transport._ws.close()
        except Exception as e:
            logger.warning(f"Error closing SignalR WebSocket: {e}")

    async def emit_execution_started(self, **kwargs) -> None:
        """Send execution started event."""
        logger.info("Execution started")
        await self._send("OnExecutionStarted", {**kwargs})

    async def emit_state_update(self, state_event: UiPathRuntimeStateEvent) -> None:
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

    async def emit_execution_suspended(
        self,
        runtime_result: UiPathRuntimeResult,
    ) -> None:
        """Send execution suspended event."""
        logger.info(f"Execution suspended: {runtime_result.status}")
        if runtime_result.trigger is None:
            return

        if runtime_result.trigger.trigger_type == UiPathResumeTriggerType.API:
            await self._send(
                "OnBreakpointHit",
                {
                    "node": "<suspended>",
                    "type": "before",
                    "state": runtime_result.output.model_dump()
                    if runtime_result.output
                    and isinstance(runtime_result.output, BaseModel)
                    else runtime_result.output or {},
                    "nextNodes": [],
                },
            )
        else:
            await self._send(
                "OnStateUpdate",
                {
                    "nodeName": "<suspended>",
                    "state": runtime_result.trigger.model_dump()
                    if runtime_result.trigger
                    else {},
                },
            )

    async def emit_execution_resumed(self, resume_data: Any) -> None:
        """Send execution resumed event."""
        logger.info("Execution resumed")
        await self._send(
            "OnStateUpdate",
            {
                "nodeName": "<resumed>",
                "state": resume_data.model_dump()
                if resume_data and isinstance(resume_data, BaseModel)
                else resume_data or {},
            },
        )

    async def emit_execution_error(
        self,
        error: str,
    ) -> None:
        """Send execution error event."""
        if not self._connected_event.is_set():
            return

        logger.error(f"Execution error: {error}")
        await self._send(
            "OnExecutionError",
            {
                "error": error,
            },
        )

    async def wait_for_resume(self) -> None:
        """Wait for resume command from server.

        Raises:
            DebuggerQuitException: If quit command is received
        """
        logger.info("Waiting for resume command...")
        self._resume_event = asyncio.Event()

        resume_task = asyncio.create_task(self._resume_event.wait())
        terminate_task = asyncio.create_task(self._terminate_event.wait())

        done, pending = await asyncio.wait(
            {resume_task, terminate_task}, return_when=asyncio.FIRST_COMPLETED
        )

        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        if terminate_task in done:
            logger.info("Terminate command received during wait")
            raise UiPathDebugQuitError("Terminate command received from server")

        logger.info("Resume command received")

    async def wait_for_terminate(self) -> None:
        """Wait for terminate command from server."""
        await self._terminate_event.wait()

    def get_breakpoints(self) -> list[str] | Literal["*"]:
        """Get nodes to suspend execution at."""
        if self.state.step_mode:
            return "*"  # Suspend at all nodes
        return list(self.state.breakpoints)  # Only suspend at breakpoints

    async def _send(self, event_name: str, data: dict[str, Any]) -> None:
        """Send message to SignalR hub via SendCommand.

        Args:
            event_name: The event/command name (e.g., "OnExecutionStarted")
            data: The data payload to send
        """
        if not self._client:
            raise RuntimeError("SignalR client not connected")
        try:
            # Wrap the event in SendCommand protocol
            # Server expects: SendCommand(event_name, json_string_of_data)
            # Use serialize_object to recursively handle Pydantic models and nested objects
            serialized_data = serialize_object(data)
            data_json = json.dumps(serialized_data)
            arguments: list[Any] = [event_name, data_json]
            await self._client.send(method="SendCommand", arguments=arguments)
            logger.debug(f"Sent command: {event_name}")
        except Exception as e:
            logger.error(f"Error sending command {event_name} to SignalR hub: {e}")

    async def _handle_start(self, args: list[Any]) -> None:
        """Handle Start command from SignalR server.

        Args:
            args: List containing command arguments as JSON string
        """
        if not args or len(args) == 0:
            logger.warning("Start command received with empty args.")
            return

        command_args = json.loads(args[0])
        self.state.breakpoints = set(command_args.get("breakpoints", []))
        step_mode = command_args.get("enableStepMode", False)
        self.state.step_mode = step_mode
        logger.info(
            f"Debug started: breakpoints={self.state.breakpoints}, step_mode={step_mode}"
        )

    async def _handle_resume(self, args: list[Any]) -> None:
        """Handle Resume command from SignalR server.

        Args:
            args: List containing command arguments as JSON string
        """
        if not self._resume_event:
            logger.warning("Resume command received but no resume event is waiting.")
            return

        if args and len(args) > 0:
            command_args = json.loads(args[0])
            if not command_args.get("enableStepMode", False):
                self.state.step_mode = False
                breakpoints = command_args.get("breakpoints", [])
                self.state.clear_all_breakpoints()
                self._add_breakpoints(breakpoints)
            else:
                self.state.step_mode = True

        self._resume_event.set()

    def _add_breakpoints(self, breakpoints: list[dict[str, Any]]) -> None:
        for bp in breakpoints:
            node_name = (
                bp.get("node", {}).get("name")
                if isinstance(bp.get("node"), dict)
                else None
            )
            if node_name:
                self.state.add_breakpoint(node_name)
                logger.info(f"Breakpoint added: {node_name}")
            else:
                logger.warning(f"Breakpoint without node name: {bp}")

    async def _handle_step(self, args: list[Any]) -> None:
        """Handle Step command from SignalR server.

        Args:
            args: List containing command arguments as JSON string
        """
        command_args = json.loads(args[0]) if args and len(args) > 0 else {}
        step_mode = command_args.get("enableStepMode", True)
        self.state.step_mode = step_mode

    async def _handle_add_breakpoints(self, args: list[Any]) -> None:
        """Handle AddBreakpoints command from SignalR server.

        Args:
            args: List containing command arguments as JSON string with breakpoints list
        """
        if not args or len(args) == 0:
            logger.warning("AddBreakpoints command received with empty args.")
            return

        command_args = json.loads(args[0])
        breakpoints = command_args.get("breakpoints", [])

        self._add_breakpoints(breakpoints)

    async def _handle_remove_breakpoints(self, args: list[Any]) -> None:
        """Handle RemoveBreakpoints command from SignalR server.

        Args:
            args: List containing command arguments as JSON string with breakpoints list
        """
        if not args or len(args) == 0:
            self.state.clear_all_breakpoints()
            logger.info("All breakpoints cleared")
            return

        command_args = json.loads(args[0])
        break_points = command_args.get("breakpoints", [])

        if not break_points:
            self.state.clear_all_breakpoints()
            logger.info("All breakpoints cleared")
        else:
            for bp in break_points:
                node_name = (
                    bp.get("node", {}).get("name")
                    if isinstance(bp.get("node"), dict)
                    else None
                )
                if node_name:
                    self.state.remove_breakpoint(node_name)
                    logger.info(f"Breakpoint removed: {node_name}")

    async def _handle_quit(self, _args: list[Any]) -> None:
        """Handle Quit command from SignalR server."""
        logger.info("Quit command received")
        self._terminate_event.set()

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


def get_remote_debug_bridge(context: UiPathRuntimeContext) -> UiPathDebugBridgeProtocol:
    """Factory to get SignalR debug bridge for remote debugging."""
    uipath_url = os.environ.get("UIPATH_URL")
    if not uipath_url or not context.job_id:
        raise ValueError(
            "UIPATH_URL and UIPATH_JOB_KEY are required for remote debugging"
        )

    signalr_url = f"{uipath_url.rstrip('/')}/orchestrator_/signalr/robotdebug?sessionId={context.job_id}"

    return SignalRDebugBridge(
        hub_url=signalr_url,
        access_token=os.environ.get("UIPATH_ACCESS_TOKEN"),
        headers={
            "X-UiPath-Internal-TenantId": context.tenant_id or "",
            "X-UiPath-Internal-AccountId": context.org_id or "",
            "X-UiPath-FolderKey": context.folder_key or "",
        },
    )


def get_debug_bridge(
    context: UiPathRuntimeContext, verbose: bool = True
) -> UiPathDebugBridgeProtocol:
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
