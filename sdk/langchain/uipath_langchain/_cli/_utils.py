import json
import logging
import sys
from typing import Any, Dict

logging.basicConfig(stream=sys.stderr, level=logging.INFO)
logger = logging.getLogger(__name__)

def load_langgraph_config(config_path: str = "langgraph.json") -> Dict[str, Any]:
    """Load the langgraph configuration file."""
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)

        if 'graphs' not in config:
            raise ValueError("No 'graphs' field found in langgraph.json")

        return config
    except Exception as e:
        logger.error(f"[Executor] Failed to load langgraph.json: {str(e)}")
        raise
