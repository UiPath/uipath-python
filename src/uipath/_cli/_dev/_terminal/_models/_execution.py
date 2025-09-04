import os
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from rich.text import Text

from ...._runtime._contracts import UiPathErrorContract
from ._messages import LogMessage, TraceMessage


class ExecutionRun:
    """Represents a single execution run."""

    def __init__(self, entrypoint: str, input_data: str):
        self.id = str(uuid4())[:8]
        self.entrypoint = entrypoint
        self.input_data = input_data
        self.output_data: Optional[str] = None
        self.start_time = datetime.now()
        self.end_time: Optional[datetime] = None
        self.status = "running"  # running, completed, failed
        self.traces: List[TraceMessage] = []
        self.logs: List[LogMessage] = []
        self.error: Optional[UiPathErrorContract] = None

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
            "completed": "green",
            "failed": "red",
        }

        status_icon = {
            "running": "▶",
            "completed": "✔",
            "failed": "✖",
        }.get(self.status, "?")

        script_name = (
            os.path.basename(self.entrypoint) if self.entrypoint else "untitled"
        )
        time_str = self.start_time.strftime("%H:%M:%S")
        duration_str = str(self.duration)

        icon_width = 2
        script_width = 10
        time_width = 8
        dur_width = 6

        text = Text()
        text.append(
            f"{status_icon:<{icon_width}} ",
            style=status_colors.get(self.status, "white"),
        )
        text.append(f"{script_name:<{script_width}.{script_width}} ")
        text.append(f"({time_str:<{time_width}}) ")
        text.append(f"[{duration_str:<{dur_width}}]")

        return text
