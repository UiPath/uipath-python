import logging
import os
import sys
from contextvars import ContextVar
from typing import Optional, TextIO, Union, cast

# Context variable to track current execution_id
current_execution_id: ContextVar[Optional[str]] = ContextVar(
    "current_execution_id", default=None
)


class ExecutionLogHandler(logging.Handler):
    """Handler for an execution unit."""

    def __init__(self, execution_id: str):
        """Initialize the buffered handler."""
        super().__init__()
        self.execution_id: str = execution_id
        self.buffer: list[logging.LogRecord] = []
        self.setFormatter(logging.Formatter("[%(asctime)s][%(levelname)s] %(message)s"))

    def emit(self, record: logging.LogRecord):
        """Store log record in buffer grouped by execution_id."""
        self.buffer.append(record)

    def flush_execution_logs(self, target_handler: logging.Handler) -> None:
        """Flush buffered logs to a target handler.

        Args:
            target_handler: The handler to write the logs to
        """
        for record in self.buffer:
            target_handler.handle(record)
        target_handler.flush()

    def clear_execution(self) -> None:
        """Clear buffered logs without writing them."""
        self.buffer.clear()


class PersistentLogsHandler(logging.FileHandler):
    """A simple log handler that always writes to a single file without rotation."""

    def __init__(self, file: str):
        """Initialize the handler to write logs to a single file, appending always.

        Args:
            file (str): The file where logs should be stored.
        """
        # Open file in append mode ('a'), so logs are not overwritten
        super().__init__(file, mode="a", encoding="utf8")

        self.formatter = logging.Formatter("[%(asctime)s][%(levelname)s] %(message)s")
        self.setFormatter(self.formatter)


class ExecutionContextFilter(logging.Filter):
    """Filter that only allows logs from a specific execution context."""

    def __init__(self, execution_id: str):
        super().__init__()
        self.execution_id = execution_id

    def filter(self, record: logging.LogRecord) -> bool:
        """Allow logs that have matching execution_id attribute or context."""
        # First check if record has execution_id attribute
        record_execution_id = getattr(record, "execution_id", None)
        if record_execution_id == self.execution_id:
            return True

        # Fall back to context variable
        ctx_execution_id = current_execution_id.get()
        if ctx_execution_id == self.execution_id:
            # Inject execution_id into record for downstream handlers
            record.execution_id = self.execution_id
            return True

        return False


class MasterExecutionFilter(logging.Filter):
    """Filter for master handler that blocks logs from any child execution."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Block logs that belong to a child execution context."""
        ctx_execution_id = current_execution_id.get()
        # Block if there's an active child execution context
        return ctx_execution_id is None


class LogsInterceptor:
    """Intercepts all logging and stdout/stderr, routing to either persistent log files or stdout based on whether it's running as a job or not."""

    def __init__(
        self,
        min_level: Optional[str] = "INFO",
        dir: Optional[str] = "__uipath",
        file: Optional[str] = "execution.log",
        job_id: Optional[str] = None,
        is_debug_run: bool = False,
        log_handler: Optional[logging.Handler] = None,
        execution_id: Optional[str] = None,
    ):
        """Initialize the log interceptor.

        Args:
            min_level: Minimum logging level to capture.
            dir (str): The directory where logs should be stored.
            file (str): The log file name.
            job_id (str, optional): If provided, logs go to file; otherwise, to stdout.
            is_debug_run (bool, optional): If True, log the output to stdout/stderr.
            log_handler (logging.Handler, optional): Custom log handler to use.
            execution_id (str, optional): Unique identifier for this execution context.
        """
        min_level = min_level or "INFO"
        self.job_id = job_id
        self.execution_id = execution_id

        # Convert to numeric level for consistent comparison
        self.numeric_min_level = getattr(logging, min_level.upper(), logging.INFO)

        # Store the original disable level
        self.original_disable_level = logging.root.manager.disable

        self.root_logger = logging.getLogger()
        self.original_level = self.root_logger.level
        self.original_handlers = list(self.root_logger.handlers)

        # Store system stdout/stderr
        self.original_stdout = cast(TextIO, sys.stdout)
        self.original_stderr = cast(TextIO, sys.stderr)

        self.log_handler: Union[
            PersistentLogsHandler,
            logging.StreamHandler[TextIO],
            logging.Handler,
        ]

        if log_handler:
            self.log_handler = log_handler
        else:
            # Create either file handler (runtime) or stdout handler (debug)
            if is_debug_run:
                # Use stdout handler when not running as a job or eval
                self.log_handler = logging.StreamHandler(sys.stdout)
                formatter = logging.Formatter("%(message)s")
                self.log_handler.setFormatter(formatter)
            else:
                # Ensure directory exists for file logging
                dir = dir or "__uipath"
                file = file or "execution.log"
                os.makedirs(dir, exist_ok=True)
                log_file = os.path.join(dir, file)
                self.log_handler = PersistentLogsHandler(file=log_file)

        self.log_handler.setLevel(self.numeric_min_level)

        # Add execution context filter if execution_id provided
        self.execution_filter: Optional[logging.Filter] = None
        if execution_id:
            self.execution_filter = ExecutionContextFilter(execution_id)
            self.log_handler.addFilter(self.execution_filter)
        else:
            # Master execution: filter out child execution logs
            self.execution_filter = MasterExecutionFilter()
            self.log_handler.addFilter(self.execution_filter)

        self.logger = logging.getLogger("runtime")
        self.patched_loggers: set[str] = set()

    def _clean_all_handlers(self, logger: logging.Logger) -> None:
        """Remove ALL handlers from a logger except ours."""
        handlers_to_remove = list(logger.handlers)
        for handler in handlers_to_remove:
            logger.removeHandler(handler)

        # Now add our handler
        logger.addHandler(self.log_handler)

    def setup(self) -> None:
        """Configure logging to use our persistent handler."""
        # Set the context variable for this execution
        if self.execution_id:
            current_execution_id.set(self.execution_id)

        # Only use global disable if we're not in a parallel execution context
        if not self.execution_id and self.numeric_min_level > logging.NOTSET:
            logging.disable(self.numeric_min_level - 1)

        # Set root logger level
        self.root_logger.setLevel(self.numeric_min_level)

        if self.execution_id:
            # Child execution mode: add our handler without removing others
            if self.log_handler not in self.root_logger.handlers:
                self.root_logger.addHandler(self.log_handler)

            # Keep propagation enabled so logs flow through filters
            # Our ExecutionContextFilter will ensure only our logs get through our handler
            for logger_name in logging.root.manager.loggerDict:
                logger = logging.getLogger(logger_name)
                # Keep propagation enabled for filtering to work
                # logger.propagate remains True (default)
                self.patched_loggers.add(logger_name)

            # Child executions should redirect stdout/stderr to their own handler
            # This ensures print statements are captured per execution
            self._redirect_stdout_stderr()
        else:
            # Master execution mode: remove all handlers and add only ours
            self._clean_all_handlers(self.root_logger)

            # Set up propagation for all existing loggers
            for logger_name in logging.root.manager.loggerDict:
                logger = logging.getLogger(logger_name)
                logger.propagate = False  # Prevent double-logging
                self._clean_all_handlers(logger)
                self.patched_loggers.add(logger_name)

            # Master redirects stdout/stderr
            self._redirect_stdout_stderr()

    def _redirect_stdout_stderr(self) -> None:
        """Redirect stdout and stderr to the logging system."""

        class LoggerWriter:
            def __init__(
                self,
                logger: logging.Logger,
                level: int,
                min_level: int,
                sys_file: TextIO,
            ):
                self.logger = logger
                self.level = level
                self.min_level = min_level
                self.buffer = ""
                self.sys_file = sys_file

            def write(self, message: str) -> None:
                self.buffer += message
                while "\n" in self.buffer:
                    line, self.buffer = self.buffer.split("\n", 1)
                    # Only log if the message is not empty and the level is sufficient
                    if line and self.level >= self.min_level:
                        # The context variable is automatically available here
                        self.logger._log(self.level, line, ())

            def flush(self) -> None:
                # Log any remaining content in the buffer on flush
                if self.buffer and self.level >= self.min_level:
                    self.logger._log(self.level, self.buffer, ())
                self.buffer = ""

            def fileno(self) -> int:
                # Return the file descriptor of the original system stdout/stderr
                try:
                    return self.sys_file.fileno()
                except Exception:
                    return -1

            def isatty(self) -> bool:
                return hasattr(self.sys_file, "isatty") and self.sys_file.isatty()

            def writable(self) -> bool:
                return True

            def __getattr__(self, name):
                # Delegate any unknown attributes to the original file
                return getattr(self.sys_file, name)

        # Set up stdout and stderr loggers
        stdout_logger = logging.getLogger("stdout")
        stderr_logger = logging.getLogger("stderr")

        if self.execution_id:
            # Child execution: add our handler to stdout/stderr loggers
            stdout_logger.propagate = False
            stderr_logger.propagate = False

            if self.log_handler not in stdout_logger.handlers:
                stdout_logger.addHandler(self.log_handler)
            if self.log_handler not in stderr_logger.handlers:
                stderr_logger.addHandler(self.log_handler)
        else:
            # Master execution: clean and set up handlers
            stdout_logger.propagate = False
            stderr_logger.propagate = False

            self._clean_all_handlers(stdout_logger)
            self._clean_all_handlers(stderr_logger)

        # Use the min_level in the LoggerWriter to filter messages
        sys.stdout = LoggerWriter(
            stdout_logger, logging.INFO, self.numeric_min_level, self.original_stdout
        )
        sys.stderr = LoggerWriter(
            stderr_logger, logging.ERROR, self.numeric_min_level, self.original_stderr
        )

    def teardown(self) -> None:
        """Restore original logging configuration."""
        # Clear the context variable
        if self.execution_id:
            current_execution_id.set(None)

        # Restore the original disable level
        if not self.execution_id:
            logging.disable(self.original_disable_level)

        # Remove our handler and filter
        if self.execution_filter:
            self.log_handler.removeFilter(self.execution_filter)

        if self.log_handler in self.root_logger.handlers:
            self.root_logger.removeHandler(self.log_handler)

        # Remove from stdout/stderr loggers
        stdout_logger = logging.getLogger("stdout")
        stderr_logger = logging.getLogger("stderr")
        if self.log_handler in stdout_logger.handlers:
            stdout_logger.removeHandler(self.log_handler)
        if self.log_handler in stderr_logger.handlers:
            stderr_logger.removeHandler(self.log_handler)

        if not self.execution_id:
            # Master execution: restore everything
            for logger_name in self.patched_loggers:
                logger = logging.getLogger(logger_name)
                if self.log_handler in logger.handlers:
                    logger.removeHandler(self.log_handler)

            self.root_logger.setLevel(self.original_level)
            for handler in self.original_handlers:
                if handler not in self.root_logger.handlers:
                    self.root_logger.addHandler(handler)

        self.log_handler.close()

        # Only restore streams if we redirected them
        if self.original_stdout and self.original_stderr:
            sys.stdout = self.original_stdout
            sys.stderr = self.original_stderr

    def __enter__(self):
        self.setup()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.logger.error(
                f"Exception occurred: {exc_val}", exc_info=(exc_type, exc_val, exc_tb)
            )
        self.teardown()
        return False
