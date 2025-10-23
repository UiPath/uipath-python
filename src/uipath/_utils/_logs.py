import logging
from typing import Optional

logger: logging.Logger = logging.getLogger("uipath")


def setup_logging(should_debug: Optional[bool] = None) -> None:
    if not logging.root.handlers and not logger.handlers:
        logging.basicConfig(
            format="%(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        logger.setLevel(logging.DEBUG if should_debug else logging.INFO)
