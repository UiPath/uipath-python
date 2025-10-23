import json
import os
from typing import Any, Dict, Tuple, cast

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Button, Select, TabbedContent, TabPane, TextArea

from ._json_input import JsonInput


def mock_json_from_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    props = schema.get("properties", {})
    required = schema.get("required", [])
    mock = {}
    for key, info in props.items():
        if "default" in info:
            mock[key] = info["default"]
            continue
        t = info.get("type")
        if t == "string":
            mock[key] = f"example_{key}" if key in required else ""
        elif t == "integer":
            mock[key] = 0 if key in required else None
        elif t == "boolean":
            mock[key] = True if key in required else False
        elif t == "array":
            item_schema = info.get("items", {"type": "string"})
            mock[key] = [mock_json_from_schema(item_schema)]
        elif t == "object":
            mock[key] = mock_json_from_schema(info)
        else:
            mock[key] = None
    return mock


class NewRunPanel(Container):
    """Panel for creating new runs with a Select entrypoint selector."""

    selected_entrypoint = reactive("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        json_path = os.path.join(os.getcwd(), "uipath.json")
        with open(json_path, "r") as f:
            data = json.load(f)

        self.entrypoints = data.get("entryPoints", [])
        self.entrypoint_paths = [ep["filePath"] for ep in self.entrypoints]
        self.conversational = False
        self.selected_entrypoint = (
            self.entrypoint_paths[0] if self.entrypoint_paths else ""
        )
        ep: Dict[str, Any] = next(
            (
                ep
                for ep in self.entrypoints
                if ep["filePath"] == self.selected_entrypoint
            ),
            {},
        )
        self.initial_input = json.dumps(
            mock_json_from_schema(ep.get("input", {})), indent=2
        )

    def compose(self) -> ComposeResult:
        with TabbedContent():
            with TabPane("New run", id="new-tab"):
                with Vertical():
                    options = [(path, path) for path in self.entrypoint_paths]
                    yield Select(
                        options,
                        id="entrypoint-select",
                        value=self.selected_entrypoint,
                        allow_blank=False,
                    )

                    yield JsonInput(
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

    async def on_select_changed(self, event: Select.Changed) -> None:
        """Update JSON input when user selects an entrypoint."""
        self.selected_entrypoint = cast(str, event.value)

        ep: Dict[str, Any] = next(
            (
                ep
                for ep in self.entrypoints
                if ep["filePath"] == self.selected_entrypoint
            ),
            {},
        )
        json_input = self.query_one("#json-input", TextArea)
        json_input.text = json.dumps(
            mock_json_from_schema(ep.get("input", {})), indent=2
        )

    def get_input_values(self) -> Tuple[str, str, bool]:
        json_input = self.query_one("#json-input", TextArea)
        return self.selected_entrypoint, json_input.text.strip(), self.conversational

    def reset_form(self):
        """Reset selection and JSON input to defaults."""
        self.selected_entrypoint = (
            self.entrypoint_paths[0] if self.entrypoint_paths else ""
        )
        select = self.query_one("#entrypoint-select", Select)
        select.value = self.selected_entrypoint

        ep: Dict[str, Any] = next(
            (
                ep
                for ep in self.entrypoints
                if ep["filePath"] == self.selected_entrypoint
            ),
            {},
        )
        json_input = self.query_one("#json-input", TextArea)
        json_input.text = json.dumps(
            mock_json_from_schema(ep.get("input", {})), indent=2
        )
