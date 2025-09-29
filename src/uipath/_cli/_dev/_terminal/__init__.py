import asyncio
import json
import traceback
from datetime import datetime
from os import environ as env
from pathlib import Path
from typing import Any, Dict, cast
from uuid import uuid4

import pyperclip  # type: ignore[import-untyped]
from rich.traceback import Traceback
from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.widgets import Button, Footer, Input, ListView, RichLog

from uipath.agent.conversation import (
    UiPathConversationContentPart,
    UiPathConversationEvent,
    UiPathConversationMessage,
    UiPathInlineValue,
)

from ..._runtime._contracts import (
    UiPathErrorContract,
    UiPathRuntimeContext,
    UiPathRuntimeError,
    UiPathRuntimeFactory,
    UiPathRuntimeStatus,
)
from ..._utils._common import load_environment_variables
from ._components._details import RunDetailsPanel
from ._components._history import RunHistoryPanel
from ._components._new import NewRunPanel
from ._models._execution import ExecutionRun
from ._models._messages import LogMessage, TraceMessage
from ._utils._chat import RunContextChatHandler, build_user_message_event
from ._utils._exporter import RunContextExporter
from ._utils._logger import RunContextLogHandler, patch_textual_stderr


class UiPathDevTerminal(App[Any]):
    """UiPath debugging terminal interface."""

    TITLE = "UiPath Debugging Terminal"
    SUB_TITLE = "Interactive debugging interface for UiPath Python projects"
    CSS_PATH = Path(__file__).parent / "_styles" / "terminal.tcss"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("n", "new_run", "New"),
        Binding("r", "execute_run", "Run"),
        Binding("c", "copy", "Copy"),
        Binding("h", "clear_history", "Clear History"),
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(
        self,
        runtime_factory: UiPathRuntimeFactory[Any, Any],
        **kwargs,
    ):
        self._stderr_write_fd: int = patch_textual_stderr(self._add_subprocess_log)

        super().__init__(**kwargs)

        self.initial_entrypoint: str = "main.py"
        self.initial_input: str = '{\n  "message": "Hello World"\n}'
        self.runs: Dict[str, ExecutionRun] = {}
        self.runtime_factory = runtime_factory
        self.runtime_factory.add_span_exporter(
            RunContextExporter(
                on_trace=self._handle_trace_message,
                on_log=self._handle_log_message,
            ),
            batch=False,
        )

    def compose(self) -> ComposeResult:
        with Horizontal():
            # Left sidebar - run history
            with Container(classes="run-history"):
                yield RunHistoryPanel(id="history-panel")

            # Main content area
            with Container(classes="main-content"):
                # New run panel (initially visible)
                yield NewRunPanel(
                    id="new-run-panel",
                    classes="new-run-panel",
                )

                # Run details panel (initially hidden)
                yield RunDetailsPanel(id="details-panel", classes="hidden")

        yield Footer()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if event.button.id == "new-run-btn":
            await self.action_new_run()
        elif event.button.id == "execute-btn":
            await self.action_execute_run()
        elif event.button.id == "cancel-btn":
            await self.action_cancel()

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle run selection from history."""
        if event.list_view.id == "run-list" and event.item:
            run_id = getattr(event.item, "run_id", None)
            if run_id:
                history_panel = self.query_one("#history-panel", RunHistoryPanel)
                run = history_panel.get_run_by_id(run_id)
                if run:
                    self._show_run_details(run)

    @on(Input.Submitted, "#chat-input")
    async def handle_chat_input(self, event: Input.Submitted) -> None:
        """Handle user submitting text into the chat."""
        user_text = event.value.strip()
        if not user_text:
            return

        details_panel = self.query_one("#details-panel", RunDetailsPanel)
        if details_panel and details_panel.current_run:
            status = details_panel.current_run.status
            if status == "running":
                self.app.notify(
                    "Wait for agent response...", timeout=1.5, severity="warning"
                )
                return
            self._handle_chat_event(
                build_user_message_event(
                    user_text=user_text,
                    conversation_id=details_panel.current_run.id,
                ),
                details_panel.current_run.id,
            )
            if details_panel.current_run.status == "suspended":
                details_panel.current_run.resume_data = user_text
            else:
                details_panel.current_run.input_data = UiPathConversationMessage(
                    message_id=str(uuid4()),
                    created_at=datetime.now().isoformat(),
                    updated_at=datetime.now().isoformat(),
                    content_parts=[
                        UiPathConversationContentPart(
                            content_part_id=str(uuid4()),
                            mime_type="text/plain",
                            data=UiPathInlineValue(inline=user_text),
                        )
                    ],
                    role="user",
                )
            asyncio.create_task(self._execute_runtime(details_panel.current_run))
            event.input.clear()

    async def action_new_run(self) -> None:
        """Show new run panel."""
        new_panel = self.query_one("#new-run-panel")
        details_panel = self.query_one("#details-panel")

        new_panel.remove_class("hidden")
        details_panel.add_class("hidden")

    async def action_cancel(self) -> None:
        """Cancel and return to new run view."""
        await self.action_new_run()

    async def action_execute_run(self) -> None:
        """Execute a new run with UiPath runtime."""
        new_run_panel = self.query_one("#new-run-panel", NewRunPanel)
        entrypoint, input_data, conversational = new_run_panel.get_input_values()

        if not entrypoint:
            return

        input: Dict[str, Any] = {}
        try:
            input = json.loads(input_data)
        except json.JSONDecodeError:
            return

        run = ExecutionRun(entrypoint, input, conversational)

        self.runs[run.id] = run

        self._add_run_in_history(run)

        self._show_run_details(run)

        if not run.conversational:
            asyncio.create_task(self._execute_runtime(run))
        else:
            self._focus_chat_input()

    async def action_clear_history(self) -> None:
        """Clear run history."""
        history_panel = self.query_one("#history-panel", RunHistoryPanel)
        history_panel.clear_runs()
        await self.action_new_run()

    def action_copy(self) -> None:
        """Copy content of currently focused RichLog to clipboard and notify."""
        focused = self.app.focused
        if isinstance(focused, RichLog):
            clipboard_text = "\n".join(line.text for line in focused.lines)
            pyperclip.copy(clipboard_text)
            self.app.notify("Copied to clipboard!", timeout=1.5)
        else:
            self.app.notify("Nothing to copy here.", timeout=1.5, severity="warning")

    async def _execute_runtime(self, run: ExecutionRun):
        """Execute the script using UiPath runtime."""
        load_environment_variables()

        try:
            context: UiPathRuntimeContext = self.runtime_factory.new_context(
                entrypoint=run.entrypoint,
                trace_id=str(uuid4()),
                execution_id=run.id,
                is_conversational=run.conversational,
                logs_min_level=env.get("LOG_LEVEL", "INFO"),
                log_handler=RunContextLogHandler(
                    run_id=run.id, callback=self._handle_log_message
                ),
                chat_handler=RunContextChatHandler(
                    run_id=run.id, callback=self._handle_chat_event
                )
                if run.conversational
                else None,
            )

            if run.status == "suspended":
                context.input_json = run.resume_data
                context.resume = True
                self._add_info_log(run, f"Resuming execution: {run.entrypoint}")
            else:
                if run.conversational:
                    context.input_message = cast(
                        UiPathConversationMessage, run.input_data
                    )
                else:
                    context.input_json = run.input_data
                self._add_info_log(run, f"Starting execution: {run.entrypoint}")

            run.status = "running"
            run.start_time = datetime.now()

            result = await self.runtime_factory.execute_in_root_span(context)

            if result is not None:
                if (
                    result.status == UiPathRuntimeStatus.SUSPENDED.value
                    and result.resume
                ):
                    run.status = "suspended"
                else:
                    run.output_data = result.output
                    run.status = "completed"
                if run.output_data:
                    self._add_info_log(run, f"Execution result: {run.output_data}")

            self._add_info_log(run, "✅ Execution completed successfully")
            run.end_time = datetime.now()

        except UiPathRuntimeError as e:
            self._add_error_log(run)
            run.status = "failed"
            run.end_time = datetime.now()
            run.error = e.error_info

        except Exception as e:
            self._add_error_log(run)
            run.status = "failed"
            run.end_time = datetime.now()
            run.error = UiPathErrorContract(
                code="Unknown", title=str(e), detail=traceback.format_exc()
            )

        self._update_run_in_history(run)
        self._update_run_details(run)

    def _show_run_details(self, run: ExecutionRun):
        """Show details panel for a specific run."""
        # Hide new run panel, show details panel
        new_panel = self.query_one("#new-run-panel")
        details_panel = self.query_one("#details-panel", RunDetailsPanel)

        new_panel.add_class("hidden")
        details_panel.remove_class("hidden")

        # Populate the details panel with run data
        details_panel.update_run(run)

    def _focus_chat_input(self):
        """Focus the chat input box."""
        details_panel = self.query_one("#details-panel", RunDetailsPanel)
        details_panel.switch_tab("chat-tab")
        chat_input = details_panel.query_one("#chat-input", Input)
        chat_input.focus()

    def _add_run_in_history(self, run: ExecutionRun):
        """Add run to history panel."""
        history_panel = self.query_one("#history-panel", RunHistoryPanel)
        history_panel.add_run(run)

    def _update_run_in_history(self, run: ExecutionRun):
        """Update run display in history panel."""
        history_panel = self.query_one("#history-panel", RunHistoryPanel)
        history_panel.update_run(run)

    def _update_run_details(self, run: ExecutionRun):
        """Update the displayed run information."""
        details_panel = self.query_one("#details-panel", RunDetailsPanel)
        details_panel.update_run_details(run)

    def _handle_trace_message(self, trace_msg: TraceMessage):
        """Handle trace message from exporter."""
        run = self.runs[trace_msg.run_id]
        for i, existing_trace in enumerate(run.traces):
            if existing_trace.span_id == trace_msg.span_id:
                run.traces[i] = trace_msg
                break
        else:
            run.traces.append(trace_msg)

        details_panel = self.query_one("#details-panel", RunDetailsPanel)
        details_panel.add_trace(trace_msg)

    def _handle_log_message(self, log_msg: LogMessage):
        """Handle log message from exporter."""
        self.runs[log_msg.run_id].logs.append(log_msg)
        details_panel = self.query_one("#details-panel", RunDetailsPanel)
        details_panel.add_log(log_msg)

    def _handle_chat_event(
        self, event: UiPathConversationEvent, execution_id: str
    ) -> None:
        updated_chat_message = self.runs[execution_id].add_message(event)
        if not updated_chat_message:
            return
        details_panel = self.app.query_one("#details-panel", RunDetailsPanel)
        details_panel.add_chat_message(event, updated_chat_message, execution_id)

    def _add_info_log(self, run: ExecutionRun, message: str):
        """Add info log to run."""
        timestamp = datetime.now()
        log_msg = LogMessage(run.id, "INFO", message, timestamp)
        self._handle_log_message(log_msg)

    def _add_error_log(self, run: ExecutionRun):
        """Add error log to run."""
        timestamp = datetime.now()
        tb = Traceback(
            show_locals=False,
            max_frames=4,
        )
        log_msg = LogMessage(run.id, "ERROR", tb, timestamp)
        self._handle_log_message(log_msg)

    def _add_subprocess_log(self, level: str, message: str) -> None:
        """Handle a stderr line coming from subprocesses."""

        def add_log() -> None:
            details_panel = self.query_one("#details-panel", RunDetailsPanel)
            run = getattr(details_panel, "current_run", None)
            if run:
                log_msg = LogMessage(run.id, level, message, datetime.now())
                self._handle_log_message(log_msg)

        self.call_from_thread(add_log)
