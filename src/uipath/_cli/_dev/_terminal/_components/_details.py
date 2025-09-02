from typing import Dict, List, Optional

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import RichLog, TabbedContent, TabPane, Tree
from textual.widgets.tree import TreeNode

from .._models._execution import ExecutionRun
from .._models._messages import LogMessage, TraceMessage


class SpanDetailsDisplay(Container):
    """Widget to display details of a selected span."""

    def compose(self) -> ComposeResult:
        yield RichLog(
            id="span-details",
            max_lines=1000,
            highlight=True,
            markup=True,
            classes="detail-log",
        )

    def show_span_details(self, trace_msg: TraceMessage):
        """Display detailed information about a trace span."""
        details_log = self.query_one("#span-details", RichLog)
        details_log.clear()

        # Format span details
        details_log.write(f"[bold cyan]Span: {trace_msg.span_name}[/bold cyan]")
        details_log.write(f"[dim]Trace ID: {trace_msg.trace_id}[/dim]")
        details_log.write(f"[dim]Span ID: {trace_msg.span_id}[/dim]")
        details_log.write(f"[dim]Run ID: {trace_msg.run_id}[/dim]")

        if trace_msg.parent_span_id:
            details_log.write(f"[dim]Parent Span: {trace_msg.parent_span_id}[/dim]")

        details_log.write("")  # Empty line

        # Status with color
        color_map = {
            "started": "blue",
            "running": "yellow",
            "completed": "green",
            "failed": "red",
            "error": "red",
        }
        color = color_map.get(trace_msg.status.lower(), "white")
        details_log.write(f"Status: [{color}]{trace_msg.status.upper()}[/{color}]")

        # Timestamps
        details_log.write(
            f"Started: [dim]{trace_msg.timestamp.strftime('%H:%M:%S.%f')[:-3]}[/dim]"
        )

        if trace_msg.duration_ms is not None:
            details_log.write(
                f"Duration: [yellow]{trace_msg.duration_ms:.2f}ms[/yellow]"
            )

        # Additional attributes if available
        if trace_msg.attributes:
            details_log.write("")
            details_log.write("[bold]Attributes:[/bold]")
            for key, value in trace_msg.attributes.items():
                details_log.write(f"  {key}: {value}")


class RunDetailsPanel(Container):
    """Panel showing traces and logs for selected run with tabbed interface."""

    current_run: reactive[Optional[ExecutionRun]] = reactive(None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.span_tree_nodes = {}  # Map span_id to tree nodes
        self.current_run = None  # Store reference to current run

    def compose(self) -> ComposeResult:
        with TabbedContent():
            # Run details tab
            with TabPane("Details", id="run-tab"):
                yield RichLog(
                    id="run-details-log",
                    max_lines=1000,
                    highlight=True,
                    markup=True,
                    classes="detail-log",
                )

            # Traces tab
            with TabPane("Traces", id="traces-tab"):
                with Horizontal(classes="traces-content"):
                    # Left side - Span tree
                    with Vertical(
                        classes="spans-tree-section", id="spans-tree-container"
                    ):
                        yield Tree("Trace", id="spans-tree", classes="spans-tree")

                    # Right side - Span details
                    with Vertical(classes="span-details-section"):
                        yield SpanDetailsDisplay(id="span-details-display")

            # Logs tab
            with TabPane("Logs", id="logs-tab"):
                yield RichLog(
                    id="logs-log",
                    max_lines=1000,
                    highlight=True,
                    markup=True,
                    classes="detail-log",
                )

    def watch_current_run(
        self, old_value: Optional[ExecutionRun], new_value: Optional[ExecutionRun]
    ):
        """Watch for changes to the current run."""
        if new_value is not None:
            if old_value != new_value:
                self.current_run = new_value
                self.show_run(new_value)

    def update_run(self, run: ExecutionRun):
        """Update the displayed run information."""
        self.current_run = run

    def show_run(self, run: ExecutionRun):
        """Display traces and logs for a specific run."""
        # Populate run details tab
        self._show_run_details(run)

        # Populate logs - convert string logs to display format
        logs_log = self.query_one("#logs-log", RichLog)
        logs_log.clear()
        for log in run.logs:
            self.add_log(log)

        # Clear and rebuild traces tree using TraceMessage objects
        self._rebuild_spans_tree()

    def _show_run_details(self, run: ExecutionRun):
        """Display detailed information about the run in the Details tab."""
        run_details_log = self.query_one("#run-details-log", RichLog)
        run_details_log.clear()

        # Run header
        run_details_log.write(f"[bold cyan]Run ID: {run.id}[/bold cyan]")
        run_details_log.write("")

        # Run status with color
        status_color_map = {
            "started": "blue",
            "running": "yellow",
            "completed": "green",
            "failed": "red",
            "error": "red",
        }
        status = getattr(run, "status", "unknown")
        color = status_color_map.get(status.lower(), "white")
        run_details_log.write(
            f"[bold]Status:[/bold] [{color}]{status.upper()}[/{color}]"
        )

        # Timestamps
        if hasattr(run, "start_time") and run.start_time:
            run_details_log.write(
                f"[bold]Started:[/bold] [dim]{run.start_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}[/dim]"
            )

        if hasattr(run, "end_time") and run.end_time:
            run_details_log.write(
                f"[bold]Ended:[/bold] [dim]{run.end_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}[/dim]"
            )

        # Duration
        if hasattr(run, "duration_ms") and run.duration_ms is not None:
            run_details_log.write(
                f"[bold]Duration:[/bold] [yellow]{run.duration_ms:.2f}ms[/yellow]"
            )
        elif (
            hasattr(run, "start_time")
            and hasattr(run, "end_time")
            and run.start_time
            and run.end_time
        ):
            duration = (run.end_time - run.start_time).total_seconds() * 1000
            run_details_log.write(
                f"[bold]Duration:[/bold] [yellow]{duration:.2f}ms[/yellow]"
            )

        run_details_log.write("")

        # Input section
        if hasattr(run, "input_data") and run.input_data is not None:
            run_details_log.write("[bold green]INPUT:[/bold green]")
            run_details_log.write("[dim]" + "=" * 50 + "[/dim]")

            # Handle different input types
            if isinstance(run.input_data, str):
                run_details_log.write(run.input_data)
            elif isinstance(run.input_data, dict):
                import json

                run_details_log.write(json.dumps(run.input_data, indent=2))
            else:
                run_details_log.write(str(run.input_data))

            run_details_log.write("")

        # Output section
        if hasattr(run, "output_data") and run.output_data is not None:
            run_details_log.write("[bold magenta]OUTPUT:[/bold magenta]")
            run_details_log.write("[dim]" + "=" * 50 + "[/dim]")

            # Handle different output types
            if isinstance(run.output_data, str):
                run_details_log.write(run.output_data)
            elif isinstance(run.output_data, dict):
                import json

                run_details_log.write(json.dumps(run.output_data, indent=2))
            else:
                run_details_log.write(str(run.output_data))

            run_details_log.write("")

        # Error section (if applicable)
        if hasattr(run, "error") and run.error:
            run_details_log.write("[bold red]ERROR:[/bold red]")
            run_details_log.write("[dim]" + "=" * 50 + "[/dim]")
            if run.error.code:
                run_details_log.write(f"[red]Code: {run.error.code}[/red]")
            run_details_log.write(f"[red]Title: {run.error.title}[/red]")
            run_details_log.write(f"[red]\n{run.error.detail}[/red]")
            run_details_log.write("")

        # Additional metadata
        run_details_log.write("[bold]METADATA:[/bold]")
        run_details_log.write("[dim]" + "=" * 50 + "[/dim]")

        # Show available attributes
        for attr in ["id", "status", "start_time", "end_time", "duration_ms"]:
            if hasattr(run, attr):
                value = getattr(run, attr)
                if value is not None:
                    run_details_log.write(f"  {attr}: {value}")

        # Show traces count
        traces_count = len(run.traces) if run.traces else 0
        run_details_log.write(f"  traces_count: {traces_count}")

        # Show logs count
        logs_count = len(run.logs) if run.logs else 0
        run_details_log.write(f"  logs_count: {logs_count}")

    def _rebuild_spans_tree(self):
        """Rebuild the spans tree from current run's traces."""
        spans_tree = self.query_one("#spans-tree", Tree)
        spans_tree.clear()
        # Only clear the node mapping since we're rebuilding the tree structure
        self.span_tree_nodes.clear()

        if not self.current_run or not self.current_run.traces:
            return

        # Build spans tree from TraceMessage objects
        self._build_spans_tree(self.current_run.traces)

        # Expand the root "Trace" node
        spans_tree.root.expand()

    def _build_spans_tree(self, trace_messages: list[TraceMessage]):
        """Build the spans tree from trace messages."""
        spans_tree = self.query_one("#spans-tree", Tree)
        root = spans_tree.root

        # Filter out spans without parents (artificial root spans)
        spans_by_id = {
            msg.span_id: msg for msg in trace_messages if msg.parent_span_id is not None
        }

        # Build parent-to-children mapping once upfront
        children_by_parent: Dict[str, List[TraceMessage]] = {}
        for msg in spans_by_id.values():
            if msg.parent_span_id:
                if msg.parent_span_id not in children_by_parent:
                    children_by_parent[msg.parent_span_id] = []
                children_by_parent[msg.parent_span_id].append(msg)

        # Find root spans (parent doesn't exist in our filtered data)
        root_spans = [
            msg
            for msg in trace_messages
            if msg.parent_span_id and msg.parent_span_id not in spans_by_id
        ]

        # Build tree recursively for each root span
        for root_span in sorted(root_spans, key=lambda x: x.timestamp):
            self._add_span_with_children(root, root_span, children_by_parent)

    def _add_span_with_children(
        self,
        parent_node: TreeNode[str],
        trace_msg: TraceMessage,
        children_by_parent: Dict[str, List[TraceMessage]],
    ):
        """Recursively add a span and all its children."""
        # Create the node for this span
        color_map = {
            "started": "🔵",
            "running": "🟡",
            "completed": "🟢",
            "failed": "🔴",
            "error": "🔴",
        }
        status_icon = color_map.get(trace_msg.status.lower(), "⚪")
        duration_str = (
            f" ({trace_msg.duration_ms:.1f}ms)" if trace_msg.duration_ms else ""
        )
        label = f"{status_icon} {trace_msg.span_name}{duration_str}"

        node = parent_node.add(label)
        node.data = trace_msg.span_id
        self.span_tree_nodes[trace_msg.span_id] = node
        node.expand()

        # Get children from prebuilt mapping - O(1) lookup
        children = children_by_parent.get(trace_msg.span_id, [])
        for child in sorted(children, key=lambda x: x.timestamp):
            self._add_span_with_children(node, child, children_by_parent)

    def on_tree_node_selected(self, event: Tree.NodeSelected[str]) -> None:
        """Handle span selection in the tree."""
        # Check if this is our spans tree
        spans_tree = self.query_one("#spans-tree", Tree)
        if event.control != spans_tree:
            return

        # Get the selected span data
        if hasattr(event.node, "data") and event.node.data:
            span_id = event.node.data
            # Find the trace in current_run.traces
            trace_msg = None
            if self.current_run:
                for trace in self.current_run.traces:
                    if trace.span_id == span_id:
                        trace_msg = trace
                        break

            if trace_msg:
                # Show span details
                span_details_display = self.query_one(
                    "#span-details-display", SpanDetailsDisplay
                )
                span_details_display.show_span_details(trace_msg)

    def update_run_details(self, run: ExecutionRun):
        if not self.current_run or run.id != self.current_run.id:
            return

        self._show_run_details(run)

    def add_trace(self, trace_msg: TraceMessage):
        """Add trace to current run if it matches."""
        if not self.current_run or trace_msg.run_id != self.current_run.id:
            return

        # Rebuild the tree to include new trace
        self._rebuild_spans_tree()

    def add_log(self, log_msg: LogMessage):
        """Add log to current run if it matches."""
        if not self.current_run or log_msg.run_id != self.current_run.id:
            return

        color_map = {
            "DEBUG": "dim cyan",
            "INFO": "blue",
            "WARN": "yellow",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "bold red",
        }

        color = color_map.get(log_msg.level.upper(), "white")
        timestamp_str = log_msg.timestamp.strftime("%H:%M:%S")
        level_short = log_msg.level[:4].upper()

        log_text = (
            f"[dim]{timestamp_str}[/dim] "
            f"[{color}]{level_short}[/{color}] "
            f"{log_msg.message}"
        )

        logs_log = self.query_one("#logs-log", RichLog)
        logs_log.write(log_text)

    def clear_display(self):
        """Clear both traces and logs display."""
        run_details_log = self.query_one("#run-details-log", RichLog)
        logs_log = self.query_one("#logs-log", RichLog)
        spans_tree = self.query_one("#spans-tree", Tree)

        run_details_log.clear()
        logs_log.clear()
        spans_tree.clear()

        self.current_run = None
        self.span_tree_nodes.clear()

        # Clear span details
        span_details_display = self.query_one(
            "#span-details-display", SpanDetailsDisplay
        )
        span_details_log = span_details_display.query_one("#span-details", RichLog)
        span_details_log.clear()

    def refresh_display(self):
        """Refresh the display with current run data."""
        if self.current_run:
            self.show_run(self.current_run)
