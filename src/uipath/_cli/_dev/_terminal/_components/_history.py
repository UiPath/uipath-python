from typing import List, Optional

from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import (
    Button,
    ListItem,
    ListView,
    Static,
    TabbedContent,
    TabPane,
)

from .._models._execution import ExecutionRun


class RunHistoryPanel(Container):
    """Left panel showing execution run history."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.runs: List[ExecutionRun] = []
        self.selected_run: Optional[ExecutionRun] = None

    def compose(self) -> ComposeResult:
        with TabbedContent():
            with TabPane("History", id="history-tab"):
                with Vertical():
                    yield ListView(id="run-list", classes="run-list")
                    yield Button(
                        "+ New",
                        id="new-run-btn",
                        variant="primary",
                        classes="new-run-btn",
                    )

    def on_mount(self) -> None:
        # Update only running items every 5 seconds
        self.set_interval(5.0, self._refresh_running_items)

    def add_run(self, run: ExecutionRun):
        """Add a new run to history."""
        self.runs.insert(0, run)  # Add to top
        self.refresh_list()

    def update_run(self, run: ExecutionRun):
        """Update an existing run."""
        self.refresh_list()

    def refresh_list(self):
        """Refresh the run list display."""
        run_list = self.query_one("#run-list", ListView)
        run_list.clear()

        for run in self.runs:
            item = ListItem(
                Static(run.display_name), classes=f"run-item run-{run.status}"
            )
            # Store run id directly on the ListItem
            item.run_id = run.id  # type: ignore[attr-defined]
            run_list.append(item)

    def get_run_by_id(self, run_id: str) -> Optional[ExecutionRun]:
        """Get run by id."""
        for run in self.runs:
            if run.id == run_id:
                return run
        return None

    def clear_runs(self):
        """Clear all runs from history."""
        self.runs.clear()
        self.refresh_list()

    def _refresh_running_items(self) -> None:
        """Refresh display names for running items only."""
        if not any(run.status == "running" for run in self.runs):
            return None

        try:
            run_list = self.query_one("#run-list", ListView)
        except Exception:
            return None

        # Take a snapshot of items to avoid mid-iteration changes
        items_snapshot = list(run_list.children)

        for item in items_snapshot:
            if not hasattr(item, "run_id"):
                continue

            run = self.get_run_by_id(item.run_id)
            if not run or run.status != "running":
                continue

            # Check if item still exists in the list (wasn't removed)
            if item not in run_list.children:
                continue

            try:
                static = item.query_one(Static)
                static.update(run.display_name)
            except Exception:
                # Item structure changed or was removed
                continue
