from typing import Callable

from uipath.agent.chat import UiPathChatMessage

from ...._runtime._contracts import UiPathChatHandler


class RunContextChatHandler(UiPathChatHandler):
    """Custom chat handler that sends chat messages to CLI UI."""

    def __init__(
        self,
        run_id: str,
        on_message: Callable[[UiPathChatMessage, str], None],
    ):
        super().__init__()
        self.run_id = run_id
        self.on_message = on_message

    def on_chat_message(self, chat_msg: UiPathChatMessage) -> None:
        """Handle a chat message for a given execution run."""
        self.on_message(chat_msg, self.run_id)
