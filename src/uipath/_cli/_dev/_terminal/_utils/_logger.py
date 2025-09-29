from __future__ import annotations

import logging
import os
import re
import threading
from datetime import datetime
from typing import Callable, Pattern

from .._models._messages import LogMessage


class RunContextLogHandler(logging.Handler):
    """Custom log handler that sends logs to CLI UI."""

    def __init__(
        self,
        run_id: str,
        callback: Callable[[LogMessage], None],
    ):
        super().__init__()
        self.run_id = run_id
        self.callback = callback

    def emit(self, record: logging.LogRecord):
        """Emit a log record to CLI UI."""
        try:
            log_msg = LogMessage(
                run_id=self.run_id,
                level=record.levelname,
                message=self.format(record),
                timestamp=datetime.fromtimestamp(record.created),
            )
            self.callback(log_msg)
        except Exception:
            # Don't let logging errors crash the app
            pass


# A dispatcher is a callable that accepts (level, message) pairs
DispatchLog = Callable[[str, str], None]

LEVEL_PATTERNS: list[tuple[str, Pattern[str]]] = [
    ("DEBUG", re.compile(r"^(DEBUG)[:\s-]+", re.I)),
    ("INFO", re.compile(r"^(INFO)[:\s-]+", re.I)),
    ("WARN", re.compile(r"^(WARNING|WARN)[:\s-]+", re.I)),
    ("ERROR", re.compile(r"^(ERROR|ERRO)[:\s-]+", re.I)),
]


def patch_textual_stderr(dispatch_log: DispatchLog) -> int:
    """Redirect subprocess stderr into a provided dispatcher.

    Args:
        dispatch_log: Callable invoked with (level, message) for each stderr line.
                      This will be called from a background thread, so the caller
                      should use `App.call_from_thread` or equivalent.

    Returns:
        int: The write file descriptor for stderr (pass to subprocesses).
    """
    from textual.app import _PrintCapture

    read_fd, write_fd = os.pipe()

    # Patch fileno() so subprocesses can write to our pipe
    _PrintCapture.fileno = lambda self: write_fd  # type: ignore[method-assign]

    def read_stderr_pipe() -> None:
        with os.fdopen(read_fd, "r", buffering=1) as pipe_reader:
            try:
                for raw in pipe_reader:
                    text = raw.rstrip()
                    level: str = "ERROR"
                    message: str = text

                    # Try to parse a known level prefix
                    for lvl, pattern in LEVEL_PATTERNS:
                        m = pattern.match(text)
                        if m:
                            level = lvl
                            message = text[m.end() :]
                            break

                    dispatch_log(level, message)

            except Exception:
                # Never raise from thread
                pass

    thread = threading.Thread(
        target=read_stderr_pipe,
        daemon=True,
        name="stderr-reader",
    )
    thread.start()

    return write_fd
