import importlib.util
import inspect
import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, cast

from dotenv import load_dotenv
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph

logger = logging.getLogger(__name__)


@dataclass
class GraphConfig:
    name: str
    path: str
    file_path: str
    graph_var: str
    _graph: Optional[Union[StateGraph, CompiledStateGraph]] = None

    @classmethod
    def from_config(cls, name: str, path: str) -> "GraphConfig":
        file_path, graph_var = path.split(":")
        return cls(name=name, path=path, file_path=file_path, graph_var=graph_var)

    async def load_graph(self) -> Union[StateGraph, CompiledStateGraph]:
        """Load graph from the specified path"""
        try:
            cwd = os.path.abspath(os.getcwd())
            abs_file_path = os.path.abspath(os.path.normpath(self.file_path))

            if not abs_file_path.startswith(cwd):
                raise ValueError(
                    f"Script path must be within the current directory. Found: {self.file_path}"
                )

            if not os.path.exists(abs_file_path):
                raise FileNotFoundError(f"Script not found: {abs_file_path}")

            if cwd not in sys.path:
                sys.path.insert(0, cwd)

            module_name = Path(abs_file_path).stem
            spec = importlib.util.spec_from_file_location(module_name, abs_file_path)

            if not spec or not spec.loader:
                raise ImportError(f"Could not load module from: {abs_file_path}")

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            graph = getattr(module, self.graph_var, None)

            # Get the graph object or function
            graph_obj = getattr(module, self.graph_var, None)

            # Handle callable graph factory
            if callable(graph_obj):
                if inspect.iscoroutinefunction(graph_obj):
                    # Handle async function
                    try:
                        graph_obj = await graph_obj()
                    except RuntimeError as e:
                        raise e
                else:
                    # Call regular function
                    graph_obj = graph_obj()

            # Handle async context manager
            if (
                graph_obj is not None
                and hasattr(graph_obj, "__aenter__")
                and callable(graph_obj.__aenter__)
            ):
                self._context_manager = graph_obj
                graph = await graph_obj.__aenter__()

                # No need for atexit registration - the calling code should
                # maintain a reference to this object and call cleanup explicitly

            else:
                # Not a context manager, use directly
                graph = graph_obj

            if not isinstance(graph, (StateGraph, CompiledStateGraph)):
                raise TypeError(
                    f"Expected StateGraph, CompiledStateGraph, or a callable returning one of these, got {type(graph)}"
                )

            self._graph = graph
            return graph

        except Exception as e:
            logger.error(f"Failed to load graph {self.name}: {str(e)}")
            raise

    async def get_input_schema(self) -> Dict[str, Any]:
        """Extract input schema from graph"""
        if not self._graph:
            self._graph = await self.load_graph()

        if hasattr(self._graph, "input_schema"):
            return cast(dict[str, Any], self._graph.input_schema)
        return {}

    async def cleanup(self):
        """
        Clean up resources when done with the graph.
        This should be called when the graph is no longer needed.
        """
        if hasattr(self, "_context_manager") and self._context_manager:
            try:
                await self._context_manager.__aexit__(None, None, None)
            except Exception as e:
                logger.warning(f"Error during context cleanup: {str(e)}")
            finally:
                self._context_manager = None
                self._graph = None


class LangGraphConfig:
    def __init__(self, config_path: str = "langgraph.json"):
        self.config_path = config_path
        self._config: Optional[Dict[str, Any]] = None
        self._graphs: List[GraphConfig] = []

    @property
    def exists(self) -> bool:
        """Check if langgraph.json exists"""
        return os.path.exists(self.config_path)

    def load_config(self) -> Dict[str, Any]:
        """Load and validate langgraph configuration"""
        if not self.exists:
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        try:
            with open(self.config_path, "r") as f:
                config = json.load(f)

            required_fields = ["graphs"]
            missing_fields = [field for field in required_fields if field not in config]
            if missing_fields:
                raise ValueError(
                    f"Missing required fields in langgraph.json: {missing_fields}"
                )

            if env_file := config.get("env"):
                env_path = os.path.abspath(os.path.normpath(env_file))
                if os.path.exists(env_path):
                    if not load_dotenv(env_path):
                        # log warning only if dotenv is not empty
                        if os.path.getsize(env_path) > 0:
                            logger.warning(
                                f"Could not load environment variables from {env_path}"
                            )
                    else:
                        logger.debug(f"Loaded environment variables from {env_path}")

            self._config = config
            self._load_graphs()
            return config
        except Exception as e:
            logger.error(f"Failed to load langgraph.json: {str(e)}")
            raise

    def _load_graphs(self):
        """Load all graph configurations"""
        if not self._config:
            return

        self._graphs = [
            GraphConfig.from_config(name, path)
            for name, path in self._config["graphs"].items()
        ]

    @property
    def graphs(self) -> List[GraphConfig]:
        """Get all graph configurations"""
        if not self._graphs:
            self.load_config()
        return self._graphs

    def get_graph(self, name: str) -> Optional[GraphConfig]:
        """Get a specific graph configuration by name"""
        return next((g for g in self.graphs if g.name == name), None)

    @property
    def dependencies(self) -> List[str]:
        """Get project dependencies"""
        return self._config.get("dependencies", []) if self._config else []

    @property
    def env_file(self) -> Optional[str]:
        """Get environment file path"""
        return self._config.get("env") if self._config else None
