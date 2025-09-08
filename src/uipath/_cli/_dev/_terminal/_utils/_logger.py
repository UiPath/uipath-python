import logging
from datetime import datetime
from typing import Callable

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
