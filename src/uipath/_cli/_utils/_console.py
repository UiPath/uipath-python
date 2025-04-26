from contextlib import contextmanager
from enum import Enum
from typing import Any, Iterator, List, Optional, Type, TypeVar

import click
from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner as RichSpinner
from rich.text import Text


class LogLevel(Enum):
    """Enum for log levels with corresponding emojis."""

    INFO = ""
    SUCCESS = click.style("✓ ", fg="green", bold=True)
    WARNING = "⚠️"
    ERROR = "❌"
    HINT = "💡"
    CONFIG = "🔧"
    SELECT = "👇"
    LINK = "🔗"
    MAGIC = "✨"


T = TypeVar("T", bound="ConsoleLogger")


class ConsoleLogger:
    """A singleton wrapper class for terminal output with emoji support and spinners."""

    # Class variable to hold the singleton instance
    _instance: Optional["ConsoleLogger"] = None

    def __new__(cls: Type[T]) -> T:
        """Ensure only one instance of ConsoleLogger is created.

        Returns:
            The singleton instance of ConsoleLogger
        """
        if cls._instance is None:
            cls._instance = super(ConsoleLogger, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance  # type: ignore

    def __init__(self):
        """Initialize the ConsoleLogger (only once)."""
        # Only initialize once
        if not getattr(self, "_initialized", False):
            self._console = Console()
            self._spinner_live: Optional[Live] = None
            self._spinner = RichSpinner("dots")
            self._initialized = True

    def _stop_spinner_if_active(self) -> None:
        """Internal method to stop the spinner if it's active."""
        if self._spinner_live and self._spinner_live.is_started:
            self._spinner_live.stop()
            self._spinner_live = None

    def log(
        self, message: str, level: LogLevel = LogLevel.INFO, fg: Optional[str] = None
    ) -> None:
        """Log a message with the specified level and optional color.

        Args:
            message: The message to log
            level: The log level (determines the emoji)
            fg: Optional foreground color for the message
        """
        # Stop any active spinner before logging
        self._stop_spinner_if_active()

        if not level == LogLevel.INFO:
            emoji = level.value
            if fg:
                formatted_message = f"{emoji} {click.style(message, fg=fg)}"
            else:
                formatted_message = f"{emoji} {message}"
        else:
            formatted_message = message

        click.echo(formatted_message, err=LogLevel.ERROR in (level,))

    def success(self, message: str) -> None:
        """Log a success message."""
        self.log(message, LogLevel.SUCCESS)

    def error(self, message: str, include_traceback: bool = False) -> None:
        """Log an error message with optional traceback.

        Args:
            message: The error message to display
            include_traceback: Whether to include the current exception traceback
        """
        self.log(message, LogLevel.ERROR, "red")

        if include_traceback:
            import traceback

            click.echo(traceback.format_exc(), err=True)

        click.get_current_context().exit(1)

    def warning(self, message: str) -> None:
        """Log a warning message."""
        self.log(message, LogLevel.WARNING, "yellow")

    def info(self, message: str) -> None:
        """Log an informational message."""
        self.log(message, LogLevel.INFO)

    def hint(self, message: str) -> None:
        """Log a hint message."""
        self.log(message, LogLevel.HINT)

    def magic(self, message: str) -> None:
        """Log a magic message."""
        self.log(message, LogLevel.MAGIC, "green")

    def config(self, message: str) -> None:
        """Log a configuration message."""
        self.log(message, LogLevel.CONFIG)

    def select(self, message: str) -> None:
        """Log a selection message."""
        self.log(message, LogLevel.SELECT)

    def link(self, message: str, url: str) -> None:
        """Log a clickable link.

        Args:
            message: The message to display
            url: The URL to link to
        """
        formatted_url = f"\u001b]8;;{url}\u001b\\{url}\u001b]8;;\u001b\\"
        self.log(
            f"{message} {click.style(formatted_url, fg='bright_blue', bold=True)}",
            LogLevel.LINK,
        )

    def prompt(self, message: str, **kwargs: Any) -> Any:
        """Wrapper for click.prompt with emoji.

        Args:
            message: The prompt message
            **kwargs: Additional arguments to pass to click.prompt

        Returns:
            The user's input
        """
        # Stop any active spinner before prompting
        self._stop_spinner_if_active()

        return click.prompt(click.style(f"{message}", fg="yellow", bold=True), **kwargs)

    def display_options(
        self, options: List[Any], message: str = "Select an option:"
    ) -> None:
        """Display a list of options with indices.

        Args:
            options: List of options to display
            message: Optional message to display before the options
        """
        self.select(message)
        for idx, option in enumerate(options, start=0):
            click.echo(f"  {idx}: {option}")

    @contextmanager
    def spinner(self, message: str = "") -> Iterator[None]:
        """Context manager for spinner operations.

        Args:
            message: The message to display alongside the spinner

        Yields:
            None
        """
        try:
            # Stop any existing spinner before starting a new one
            self._stop_spinner_if_active()

            self._spinner.text = Text(message)
            self._spinner_live = Live(
                self._spinner,
                console=self._console,
                refresh_per_second=10,
                transient=False,
                auto_refresh=True,
            )
            self._spinner_live.start()
            yield
        finally:
            self._stop_spinner_if_active()

    def update_spinner(self, message: str) -> None:
        """Update the message of an active spinner.

        Args:
            message: The new message to display
        """
        if self._spinner_live and self._spinner_live.is_started:
            self._spinner.text = Text(message)

    @classmethod
    def get_instance(cls) -> "ConsoleLogger":
        """Get the singleton instance of ConsoleLogger.

        Returns:
            The singleton instance
        """
        if cls._instance is None:
            return cls()
        return cls._instance
