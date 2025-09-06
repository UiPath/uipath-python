import os
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from rich.text import Text

from uipath.agent.chat import UiPathChatMessage

from ...._runtime._contracts import UiPathErrorContract
from ._messages import LogMessage, TraceMessage


class ExecutionRun:
    """Represents a single execution run."""

    def __init__(self, entrypoint: str, input_data: Dict[str, Any]):
        self.id = str(uuid4())[:8]
        self.entrypoint = entrypoint
        self.input_data = input_data
        self.resume_data: Optional[Dict[str, Any]] = None
        self.output_data: Optional[Dict[str, Any]] = None
        self.start_time = datetime.now()
        self.end_time: Optional[datetime] = None
        self.status = "running"  # running, completed, failed, suspended
        self.traces: List[TraceMessage] = []
        self.logs: List[LogMessage] = []
        self.error: Optional[UiPathErrorContract] = None
        self.messages: Dict[str, UiPathChatMessage] = {}

    def add_message(self, msg: UiPathChatMessage) -> UiPathChatMessage:
        """Add or update a chat message (handles partial updates & token streaming)."""
        existing = self.messages.get(msg.message_id)

        if existing:
            # --- Merge/replace content parts ---
            if msg.content_parts:
                if not existing.content_parts:
                    existing.content_parts = []

                # Index existing parts by content_part_id
                part_index = {
                    getattr(part, "content_part_id", None): i
                    for i, part in enumerate(existing.content_parts)
                    if getattr(part, "content_part_id", None) is not None
                }

                for new_part in msg.content_parts:
                    cid = getattr(new_part, "content_part_id", None)

                    if cid is not None:
                        # Replace if exists, otherwise append
                        if cid in part_index:
                            existing.content_parts[part_index[cid]] = new_part
                        else:
                            existing.content_parts.append(new_part)
                    else:
                        # No ID → merge consecutive plain-text
                        if (
                            new_part.mime_type == "text/plain"
                            and existing.content_parts
                            and existing.content_parts[-1].mime_type == "text/plain"
                            and getattr(
                                existing.content_parts[-1], "content_part_id", None
                            )
                            is None
                        ):
                            existing.content_parts[-1].data += new_part.data
                        else:
                            existing.content_parts.append(new_part)

            # --- Merge/replace tool calls ---
            if msg.tool_calls:
                if not existing.tool_calls:
                    existing.tool_calls = []

                tool_index = {
                    getattr(call, "tool_call_id", None): i
                    for i, call in enumerate(existing.tool_calls)
                    if getattr(call, "tool_call_id", None) is not None
                }

                for new_call in msg.tool_calls:
                    tid = getattr(new_call, "tool_call_id", None)

                    if tid is not None:
                        if tid in tool_index:
                            existing.tool_calls[tool_index[tid]] = new_call
                        else:
                            existing.tool_calls.append(new_call)
                    else:
                        existing.tool_calls.append(new_call)

            # Update timestamps
            existing.updated_at = msg.updated_at or datetime.utcnow()
            return existing

        else:
            # First time seeing this message
            self.messages[msg.message_id] = msg
            return msg

    @property
    def duration(self) -> str:
        if self.end_time:
            delta = self.end_time - self.start_time
            return f"{delta.total_seconds():.1f}s"
        else:
            delta = datetime.now() - self.start_time
            return f"{delta.total_seconds():.1f}s"

    @property
    def display_name(self) -> Text:
        status_colors = {
            "running": "yellow",
            "suspended": "cyan",
            "completed": "green",
            "failed": "red",
        }

        status_icon = {
            "running": "▶",
            "suspended": "⏸",
            "completed": "✔",
            "failed": "✖",
        }.get(self.status, "?")

        script_name = (
            os.path.basename(self.entrypoint) if self.entrypoint else "untitled"
        )
        truncated_script = script_name[:8]
        time_str = self.start_time.strftime("%H:%M:%S")
        duration_str = self.duration[:6]

        text = Text()
        text.append(f"{status_icon:<2} ", style=status_colors.get(self.status, "white"))
        text.append(f"{truncated_script:<8} ")
        text.append(f"({time_str:<8}) ")
        text.append(f"[{duration_str:<6}]")

        return text
