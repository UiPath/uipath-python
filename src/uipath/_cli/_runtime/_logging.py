import logging
import os
import sys
from typing import Optional, TextIO, Union, cast


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


class LogsInterceptor:
    """Intercepts all logging and stdout/stderr, routing to either persistent log files or stdout based on whether it's running as a job or not."""

    def __init__(
        self,
        min_level: Optional[str] = "INFO",
        dir: Optional[str] = "__uipath",
        file: Optional[str] = "execution.log",
        job_id: Optional[str] = None,
    ):
        """Initialize the log interceptor.

        Args:
            min_level: Minimum logging level to capture.
            dir (str): The directory where logs should be stored.
            file (str): The log file name.
            job_id (str, optional): If provided, logs go to file; otherwise, to stdout.
        """
        min_level = min_level or "INFO"
        self.job_id = job_id

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

        self.log_handler: Union[PersistentLogsHandler, logging.StreamHandler[TextIO]]

        # Create either file handler (runtime) or stdout handler (debug)
        if self.job_id:
            # Ensure directory exists for file logging
            dir = dir or "__uipath"
            file = file or "execution.log"
            os.makedirs(dir, exist_ok=True)
            log_file = os.path.join(dir, file)
            self.log_handler = PersistentLogsHandler(file=log_file)
        else:
            # Use stdout handler when not running as a job
            self.log_handler = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter("[%(asctime)s][%(levelname)s] %(message)s")
            self.log_handler.setFormatter(formatter)

        self.log_handler.setLevel(self.numeric_min_level)
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
        # Use global disable to prevent all logging below our minimum level
        if self.numeric_min_level > logging.NOTSET:
            logging.disable(self.numeric_min_level - 1)

        # Set root logger level
        self.root_logger.setLevel(self.numeric_min_level)

        # Remove ALL handlers from root logger and add only ours
        self._clean_all_handlers(self.root_logger)

        # Set up propagation for all existing loggers
        for logger_name in logging.root.manager.loggerDict:
            logger = logging.getLogger(logger_name)
            logger.propagate = False  # Prevent double-logging
            self._clean_all_handlers(logger)
            self.patched_loggers.add(logger_name)

        # Set up stdout/stderr redirection
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
                self.sys_file = sys_file  # Store reference to system stdout/stderr

            def write(self, message: str) -> None:
                self.buffer += message
                while "\n" in self.buffer:
                    line, self.buffer = self.buffer.split("\n", 1)
                    # Only log if the message is not empty and the level is sufficient
                    if line and self.level >= self.min_level:
                        # Use _log to avoid potential recursive logging if logging methods are overridden
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

        # Set up stdout and stderr loggers with propagate=False
        stdout_logger = logging.getLogger("stdout")
        stdout_logger.propagate = False
        self._clean_all_handlers(stdout_logger)

        stderr_logger = logging.getLogger("stderr")
        stderr_logger.propagate = False
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
        # Restore the original disable level
        logging.disable(self.original_disable_level)

        if self.log_handler in self.root_logger.handlers:
            self.root_logger.removeHandler(self.log_handler)

        for logger_name in self.patched_loggers:
            logger = logging.getLogger(logger_name)
            if self.log_handler in logger.handlers:
                logger.removeHandler(self.log_handler)

        self.root_logger.setLevel(self.original_level)
        for handler in self.original_handlers:
            if handler not in self.root_logger.handlers:
                self.root_logger.addHandler(handler)

        self.log_handler.close()

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
