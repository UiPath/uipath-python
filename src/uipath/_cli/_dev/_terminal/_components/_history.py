from typing import List, Optional

from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import Button, ListItem, ListView, Static

from .._models._execution import ExecutionRun


class RunHistoryPanel(Container):
    """Left panel showing execution run history."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.runs: List[ExecutionRun] = []
        self.selected_run: Optional[ExecutionRun] = None

    def compose(self) -> ComposeResult:
        with Vertical():
            yield ListView(id="run-list", classes="run-list")
            yield Button(
                "+ New Run", id="new-run-btn", variant="primary", classes="new-run-btn"
            )

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
