import logging
import sys
from typing import Optional

logger: logging.Logger = logging.getLogger("uipath")


def setup_logging(should_debug: Optional[bool] = None) -> None:
    logging.basicConfig(
        format="[%(asctime)s - %(name)s:%(lineno)d - %(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger.setLevel(logging.DEBUG if should_debug else logging.INFO)
    logger.removeHandler(logging.StreamHandler(sys.stdout))
    logger.addHandler(logging.StreamHandler(sys.stderr))
