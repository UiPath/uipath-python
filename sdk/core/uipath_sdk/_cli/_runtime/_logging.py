import logging
import os
import sys
from typing import Optional, TextIO


class PersistentLogsHandler(logging.FileHandler):
    """
    A simple log handler that always writes to a single file without rotation.
    """

    def __init__(self, dir: str):
        """
        Initialize the handler to write logs to a single file, appending always.

        Args:
            dir (str): The directory where logs should be stored.
        """
        os.makedirs(dir, exist_ok=True)

        log_file = os.path.join(dir, "execution.log")

        # Open file in append mode ('a'), so logs are not overwritten
        super().__init__(log_file, mode="a", encoding="utf8")

        self.formatter = logging.Formatter("[%(asctime)s][%(levelname)s] %(message)s")
        self.setFormatter(self.formatter)


class LogsInterceptor:
    """
    Intercepts all logging and stdout/stderr, routing everything to persistent log files.
    Ensures that all output is captured regardless of how it's generated in user scripts.
    """

    def __init__(
        self, min_level: Optional[str] = "DEBUG", dir: Optional[str] = "__uipath_logs"
    ):
        """
        Initialize the log interceptor.

        Args:
            min_level: Minimum logging level to capture.
            dir (str): The directory where logs should be stored.
        """
        min_level = min_level or "DEBUG"
        dir = dir or "__uipath_logs"

        self.root_logger = logging.getLogger()
        self.original_level = self.root_logger.level
        self.original_handlers = list(self.root_logger.handlers)

        self.original_stdout: Optional[TextIO] = None
        self.original_stderr: Optional[TextIO] = None

        self.log_handler = PersistentLogsHandler(dir=dir)
        self.log_handler.setLevel(getattr(logging, min_level.upper(), logging.DEBUG))

        self.logger = logging.getLogger("runtime")

        self.original_get_logger = logging.getLogger

        self.patched_loggers: set[str] = set()

    def _clean_handlers(self, logger: logging.Logger) -> None:
        """Remove any duplicate handlers from a logger."""
        # Get all handlers of the same type as our handler
        handlers_to_remove = []
        for handler in logger.handlers:
            if isinstance(handler, PersistentLogsHandler):
                handlers_to_remove.append(handler)

        # Remove all the identified handlers
        for handler in handlers_to_remove:
            logger.removeHandler(handler)

    def _patch_existing_loggers(self) -> None:
        """
        Patch all existing loggers to use our handler.
        Ensure no duplicate handlers.
        """
        for logger_name in logging.root.manager.loggerDict:
            logger = logging.getLogger(logger_name)

            # Clean existing handlers
            self._clean_handlers(logger)

            # Add our handler
            logger.addHandler(self.log_handler)
            self.patched_loggers.add(logger_name)

    def _patch_get_logger(self) -> None:
        """
        Patch the getLogger function to ensure all new loggers use our handler.
        """
        log_handler = self.log_handler
        patched_loggers = self.patched_loggers
        clean_handlers = self._clean_handlers

        def patched_get_logger(name=None):
            logger = self.original_get_logger(name)

            # Clean existing handlers
            clean_handlers(logger)

            # Add our handler
            logger.addHandler(log_handler)
            if name:
                patched_loggers.add(name)

            return logger

        logging.getLogger = patched_get_logger

    def setup(self) -> None:
        """
        Configure logging to use our persistent handler.
        """
        self.root_logger.setLevel(logging.DEBUG)

        # Clean root logger handlers
        self._clean_handlers(self.root_logger)

        # Add our handler
        self.root_logger.addHandler(self.log_handler)

        # Now set up propagation properly
        for logger_name in logging.root.manager.loggerDict:
            logger = logging.getLogger(logger_name)
            logger.propagate = False  # Prevent double-logging

        # Patch existing loggers and getLogger
        self._patch_existing_loggers()
        self._patch_get_logger()
        self._redirect_stdout_stderr()

    def _redirect_stdout_stderr(self) -> None:
        """Redirect stdout and stderr to the logging system."""
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr

        class LoggerWriter:
            def __init__(self, logger: logging.Logger, level: int):
                self.logger = logger
                self.level = level
                self.buffer = ""

            def write(self, message: str) -> None:
                if message and message.strip():
                    self.logger.log(self.level, message.rstrip())

            def flush(self) -> None:
                pass

        # Set up stdout and stderr loggers with propagate=False
        stdout_logger = logging.getLogger("stdout")
        stdout_logger.propagate = False
        stderr_logger = logging.getLogger("stderr")
        stderr_logger.propagate = False

        # Clean handlers and add our handler
        self._clean_handlers(stdout_logger)
        self._clean_handlers(stderr_logger)
        stdout_logger.addHandler(self.log_handler)
        stderr_logger.addHandler(self.log_handler)

        sys.stdout = LoggerWriter(stdout_logger, logging.INFO)
        sys.stderr = LoggerWriter(stderr_logger, logging.ERROR)

    def teardown(self) -> None:
        """Restore original logging configuration."""
        logging.getLogger = self.original_get_logger

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

        if self.original_stdout and self.original_stderr:
            sys.stdout = self.original_stdout
            sys.stderr = self.original_stderr

        self.log_handler.close()

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
