import json

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, TextArea

from ._json_input import JsonInput


class ResumePanel(Container):
    """Panel for resuming a suspended run."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        with Vertical():
            yield JsonInput(
                text=json.dumps({"value": ""}, indent=2),
                language="json",
                id="resume-json-input",
                classes="input-field json-input",
            )
            with Horizontal(classes="run-actions"):
                yield Button(
                    "▶ Resume",
                    id="resume-btn",
                    variant="primary",
                    classes="action-btn",
                )

    def get_input_values(self) -> str:
        """Return the JSON text to resume with."""
        json_input = self.query_one("#resume-json-input", TextArea)
        return json_input.text.strip()
