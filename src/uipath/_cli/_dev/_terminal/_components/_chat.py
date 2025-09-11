import time
from typing import Dict, List, Optional, Union

from textual.app import ComposeResult
from textual.containers import Container, Vertical, VerticalScroll
from textual.widgets import Input, Markdown

from uipath._cli._dev._terminal._models._execution import ExecutionRun
from uipath.agent.conversation import (
    UiPathConversationEvent,
    UiPathConversationMessage,
    UiPathExternalValue,
    UiPathInlineValue,
)


class Prompt(Markdown):
    pass


class Response(Markdown):
    BORDER_TITLE = "🤖 ai"


class Tool(Markdown):
    BORDER_TITLE = "🛠️  tool"


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

    def update_messages(self, run: ExecutionRun) -> None:
        """Update the chat panel with messages from the given execution run."""
        chat_view = self.query_one("#chat-view")
        chat_view.remove_children()
        self._chat_widgets.clear()
        self._last_update_time.clear()

        for chat_msg in run.messages:
            self.add_chat_message(None, chat_msg, auto_scroll=False)
        chat_view.scroll_end(animate=False)

    def add_chat_message(
        self,
        event: Optional[UiPathConversationEvent],
        chat_msg: UiPathConversationMessage,
        auto_scroll: bool = True,
    ) -> None:
        """Add or update a chat message bubble."""
        chat_view = self.query_one("#chat-view")

        widget_cls: Union[type[Prompt], type[Response], type[Tool]]
        if chat_msg.role == "user":
            widget_cls = Prompt
        elif chat_msg.role == "assistant":
            widget_cls = Response
        else:
            widget_cls = Response

        parts: List[str] = []
        if chat_msg.content_parts:
            for part in chat_msg.content_parts:
                if (
                    part.mime_type.startswith("text/")
                    or part.mime_type == "application/json"
                ):
                    if isinstance(part.data, UiPathInlineValue):
                        parts.append(part.data.inline or "")
                    elif isinstance(part.data, UiPathExternalValue):
                        parts.append(f"[external: {part.data.url}]")

        text_block = "\n".join(parts).strip()
        content_lines = [f"{text_block}"] if text_block else []

        if chat_msg.tool_calls:
            widget_cls = Tool
            for call in chat_msg.tool_calls:
                status_icon = "✓" if call.result else "⚙"
                content_lines.append(f" {status_icon} **{call.name}**")

        if not content_lines:
            return

        content = "\n\n".join(content_lines)

        existing = self._chat_widgets.get(chat_msg.message_id)
        now = time.monotonic()
        last_update = self._last_update_time.get(chat_msg.message_id, 0.0)

        if existing:
            should_update = (
                event
                and event.exchange
                and event.exchange.message
                and event.exchange.message.end is not None
            )
            if should_update or now - last_update > 0.15:
                existing.update(content)
                self._last_update_time[chat_msg.message_id] = now
                if auto_scroll:
                    chat_view.scroll_end(animate=False)
        else:
            widget_instance = widget_cls(content)
            chat_view.mount(widget_instance)
            self._chat_widgets[chat_msg.message_id] = widget_instance
            self._last_update_time[chat_msg.message_id] = now
            if auto_scroll:
                chat_view.scroll_end(animate=False)
