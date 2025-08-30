import asyncio
import json
from datetime import datetime
from os import environ as env
from pathlib import Path
from typing import Dict
from uuid import uuid4

from dotenv import load_dotenv
from opentelemetry import trace
from opentelemetry.sdk.trace import Tracer, TracerProvider
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.widgets import Button, ListView

from ..._runtime._contracts import (
    UiPathRuntimeContext,
    UiPathRuntimeFactory,
    UiPathTraceContext,
)
from ..._utils._console import ConsoleLogger
from ._components._details import RunDetailsPanel
from ._components._history import RunHistoryPanel
from ._components._new import NewRunPanel
from ._models._execution import ExecutionRun
from ._models._messages import LogMessage, TraceMessage
from ._traces._exporter import RunContextExporter
from ._traces._logger import RunContextLogHandler
from ._traces._processor import RunContextProcessor

console = ConsoleLogger()
load_dotenv(override=True)


class UiPathDevTerminal(App):
    """UiPath development terminal interface."""

    CSS_PATH = Path(__file__).parent / "_styles" / "terminal.tcss"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("n", "new_run", "New Run"),
        Binding("r", "execute_run", "Execute"),
        Binding("c", "clear_history", "Clear History"),
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(
        self,
        runtime_factory: UiPathRuntimeFactory,
        **kwargs,
    ):
        super().__init__(**kwargs)

        self.initial_entrypoint: str = "main.py"
        self.initial_input: str = '{\n  "message": "Hello World"\n}'
        self.runs: Dict[str, ExecutionRun] = {}
        self.runtime_factory = runtime_factory
        self.trace_provider: TracerProvider = TracerProvider()
        self.trace_processor: RunContextProcessor = RunContextProcessor()
        self.trace_provider.add_span_processor(self.trace_processor)
        trace.set_tracer_provider(self.trace_provider)

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
                    initial_entrypoint=self.initial_entrypoint,
                    initial_input=self.initial_input,
                )

                # Run details panel (initially hidden)
                yield RunDetailsPanel(id="details-panel", classes="hidden")

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
        entrypoint, input_data = new_run_panel.get_input_values()

        if not entrypoint:
            return

        try:
            json.loads(input_data)
        except json.JSONDecodeError:
            return

        run = ExecutionRun(entrypoint, input_data)
        self.runs[run.id] = run

        self._add_run_in_history(run)

        self._show_run_details(run)

        asyncio.create_task(self._execute_runtime(run))

    async def action_clear_history(self) -> None:
        """Clear run history."""
        history_panel = self.query_one("#history-panel", RunHistoryPanel)
        history_panel.clear_runs()
        await self.action_new_run()

    async def _execute_runtime(self, run: ExecutionRun):
        """Execute the script using UiPath runtime."""
        try:
            context: UiPathRuntimeContext = self.runtime_factory.new_context(
                entrypoint=run.entrypoint,
                input=run.input_data,
                trace_id=str(uuid4()),
                tracing_enabled=False,
                trace_context=UiPathTraceContext(
                    enabled=False,
                ),
                logs_min_level=env.get("LOG_LEVEL", "INFO"),
                log_handler=RunContextLogHandler(
                    run_id=run.id, on_log=self._handle_log_message
                ),
            )

            self._add_info_log(run, f"Starting execution: {run.entrypoint}")

            trace_exporter = RunContextExporter(
                run_id=run.id,
                on_trace=self._handle_trace_message,
                on_log=self._handle_log_message,
            )
            self.trace_processor.register_exporter(run.id, trace_exporter)
            tracer: Tracer = trace.get_tracer("uipath-dev-terminal")

            with tracer.start_as_current_span("root", attributes={"run.id": run.id}):
                result = await self.runtime_factory.execute(context)
                run.output_data = result.output
                if run.output_data:
                    self._add_info_log(run, f"Execution result: {run.output_data}")

            self.trace_processor.unregister_exporter(run.id)

            self._add_info_log(run, "✅ Execution completed successfully")
            run.status = "completed"
            run.end_time = datetime.now()

        except Exception as e:
            error_msg = f"Execution failed: {str(e)}"
            self._add_error_log(run, error_msg)
            run.status = "failed"
            run.end_time = datetime.now()

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

    def _add_info_log(self, run: ExecutionRun, message: str):
        """Add info log to run."""
        timestamp = datetime.now()
        log_msg = LogMessage(run.id, "INFO", message, timestamp)
        self._handle_log_message(log_msg)

    def _add_error_log(self, run: ExecutionRun, message: str):
        """Add error log to run."""
        timestamp = datetime.now()
        log_msg = LogMessage(run.id, "ERROR", message, timestamp)
        self._handle_log_message(log_msg)
