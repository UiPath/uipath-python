import time
from typing import Dict, List, Union

from textual.app import ComposeResult
from textual.containers import Container, Vertical, VerticalScroll
from textual.widgets import Input, Markdown

from uipath.agent.conversation import (
    UiPathConversationMessage,
    UiPathExternalValue,
    UiPathInlineValue,
)


class Prompt(Markdown):
    pass


class Response(Markdown):
    BORDER_TITLE = "ai"


class Tool(Markdown):
    BORDER_TITLE = "tool"


class ChatPanel(Container):
    """Panel for displaying and interacting with chat messages."""

    _chat_widgets: Dict[str, Markdown]
    _last_update_time: Dict[str, float]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._chat_widgets = {}
        self._last_update_time = {}

    def compose(self) -> ComposeResult:
        with Vertical(id="chat-container"):
            yield VerticalScroll(id="chat-view")
            yield Input(
                placeholder="Type your message and press Enter...",
                id="chat-input",
            )

    def add_chat_message(self, chat_msg: UiPathConversationMessage) -> None:
        """Add or update a chat message bubble."""
        chat_view = self.query_one("#chat-view")

        widget_cls: Union[type[Prompt], type[Response], type[Tool]]
        if chat_msg.role == "user":
            widget_cls = Prompt
            prefix = "👤"
        elif chat_msg.role == "assistant":
            widget_cls = Response
            prefix = "🤖"
        else:
            widget_cls = Response
            prefix = "⚒️"

        parts: List[str] = []
        if chat_msg.content_parts:
            for part in chat_msg.content_parts:
                if part.mime_type.startswith("text/"):
                    if isinstance(part.data, UiPathInlineValue):
                        parts.append(part.data.inline or "")
                    elif isinstance(part.data, UiPathExternalValue):
                        # maybe fetch from URL or just show a placeholder
                        parts.append(f"[external: {part.data.url}]")

        text_block = "\n".join(parts).strip()
        content_lines = [f"{prefix} {text_block}"] if text_block else []

        if chat_msg.tool_calls:
            for call in chat_msg.tool_calls:
                args = call.arguments
                content_lines.append(f"🛠 **{call.name}**\n{args}")

        if not content_lines:
            return

        content = "\n\n".join(content_lines)

        existing = self._chat_widgets.get(chat_msg.message_id)
        now = time.monotonic()
        last_update = self._last_update_time.get(chat_msg.message_id, 0.0)

        if existing:
            if now - last_update > 0.15:
                existing.update(content)
                self._last_update_time[chat_msg.message_id] = now
                chat_view.scroll_end(animate=False)
        else:
            widget_instance = widget_cls(content)
            chat_view.mount(widget_instance)
            self._chat_widgets[chat_msg.message_id] = widget_instance
            self._last_update_time[chat_msg.message_id] = now
            chat_view.scroll_end(animate=False)
