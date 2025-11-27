import logging
from typing import Optional

logger: logging.Logger = logging.getLogger("uipath")


def setup_logging(should_debug: Optional[bool] = None) -> None:
    """Configure logging for the CLI."""
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter(
                fmt="%(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG if should_debug else logging.INFO)

        # Prevent propagation to root logger to avoid duplicate logs
        logger.propagate = False
