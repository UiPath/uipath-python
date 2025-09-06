from datetime import datetime
from typing import Any, Dict, Optional, Union

from rich.console import RenderableType
from textual.message import Message


class ExecutionMessage(Message):
    """Message sent when execution starts or completes."""

    def __init__(
        self,
        run_id: str,
        status: str,
        success: Optional[bool] = None,
        error: Optional[str] = None,
    ):
        self.run_id = run_id
        self.status = status  # "started", "completed", "failed"
        self.success = success
        self.error = error
        super().__init__()


class LogMessage(Message):
    """Message sent when a new log entry is created."""

    def __init__(
        self,
        run_id: str,
        level: str,
        message: Union[str, RenderableType],
        timestamp: Optional[datetime] = None,
    ):
        self.run_id = run_id
        self.level = level
        self.message = message
        self.timestamp = timestamp or datetime.now()
        super().__init__()


class TraceMessage(Message):
    """Message sent when a new trace entry is created."""

    def __init__(
        self,
        run_id: str,
        span_name: str,
        span_id: str,
        parent_span_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        status: str = "running",
        duration_ms: Optional[float] = None,
        timestamp: Optional[datetime] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ):
        self.run_id = run_id
        self.span_name = span_name
        self.span_id = span_id
        self.parent_span_id = parent_span_id
        self.trace_id = trace_id
        self.status = status
        self.duration_ms = duration_ms
        self.timestamp = timestamp or datetime.now()
        self.attributes = attributes or {}
        super().__init__()
