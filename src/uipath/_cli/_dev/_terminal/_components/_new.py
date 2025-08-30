from typing import Tuple

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Static, TextArea


class NewRunPanel(Container):
    """Panel for creating new runs."""

    def __init__(
        self,
        initial_entrypoint: str = "main.py",
        initial_input: str = '{\n  "message": "Hello World"\n}',
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.initial_entrypoint = initial_entrypoint
        self.initial_input = initial_input

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("Entrypoint", classes="field-label")
            yield TextArea(
                text=self.initial_entrypoint,
                id="script-input",
                classes="input-field script-input",
            )

            yield Static("Input JSON", classes="field-label")
            yield TextArea(
                text=self.initial_input,
                language="json",
                id="json-input",
                classes="input-field json-input",
            )

            with Horizontal(classes="run-actions"):
                yield Button(
                    "▶ Run",
                    id="execute-btn",
                    variant="primary",
                    classes="action-btn",
                )
                yield Button(
                    "Cancel",
                    id="cancel-btn",
                    variant="default",
                    classes="action-btn cancel-btn",
                )

    def get_input_values(self) -> Tuple[str, str]:
        """Get the current input values from the form."""
        script_input = self.query_one("#script-input", TextArea)
        json_input = self.query_one("#json-input", TextArea)

        return script_input.text.strip(), json_input.text.strip()

    def reset_form(self):
        """Reset form to initial values."""
        script_input = self.query_one("#script-input", TextArea)
        json_input = self.query_one("#json-input", TextArea)

        script_input.text = self.initial_entrypoint
        json_input.text = self.initial_input
