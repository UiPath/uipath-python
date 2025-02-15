import importlib
import logging
import os
from pathlib import Path
import sys
from ._utils import load_langgraph_config

from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph

logging.basicConfig(stream=sys.stderr, level=logging.INFO)
logger = logging.getLogger(__name__)


def init():
    config = load_langgraph_config()

    for _, graph_path in config["graphs"].items():
        try:
            file_path, graph_var = graph_path.split(":")

            if file_path.startswith("."):
                file_path = os.path.abspath(file_path)

            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Script not found: {file_path}")

            module_name = Path(file_path).stem

            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if not spec or not spec.loader:
                raise ImportError(f"Could not load module from: {file_path}")

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            graph = getattr(module, graph_var, None)
            if graph is None:
                raise AttributeError(f"Graph '{graph_var}' not found in {file_path}")

            if not isinstance(graph, (StateGraph, CompiledStateGraph)):
                raise TypeError(f"Expected StateGraph or CompiledStateGraph, got {type(graph)}")

            print(graph.get_input_jsonschema())
        except Exception as e:
            logger.error(f"[Executor] Failed to load graph: {str(e)}")
            raise


__all__ = ["init"]
