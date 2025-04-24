from typing import Optional

from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner as RichSpinner
from rich.text import Text


class Spinner:
    """A simple spinner class for terminal output using Rich with pinned spinner."""

    def __init__(self, message: str = ""):
        self.message = message
        self._console = Console()
        self._live: Optional[Live] = None
        self._spinner = RichSpinner("dots", Text(message))

    def start(self, message: str = "") -> None:
        """Start the spinner animation.

        Args:
            message: Optional new message to display.
        """
        if message:
            self.message = message
            self._spinner.text = Text(message)

        self._live = Live(
            self._spinner,
            console=self._console,
            refresh_per_second=10,
            transient=False,
            auto_refresh=True,
        )
        self._live.start()

    def stop(self) -> None:
        """Stop the spinner animation and clean up."""
        if self._live:
            self._live.stop()
