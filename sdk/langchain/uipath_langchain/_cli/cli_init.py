import json
from typing import Any, Dict, Optional, Tuple
from uipath_sdk._cli.middlewares import Middlewares
from ._utils._graph import LangGraphConfig


def generate_schema_from_graph(graph: Any) -> Dict[str, Any]:
    """Extract input/output schema from a LangGraph graph"""
    schema = {
        "input": {"type": "object", "properties": {}, "required": []},
        "output": {"type": "object", "properties": {}, "required": []},
    }

    if hasattr(graph, "input_schema"):
        if hasattr(graph.input_schema, "model_json_schema"):
            input_schema = graph.input_schema.model_json_schema()
            schema["input"]["properties"] = input_schema.get("properties", {})
            schema["input"]["required"] = input_schema.get("required", [])

    if hasattr(graph, "output_schema"):
        if hasattr(graph.output_schema, "model_json_schema"):
            output_schema = graph.output_schema.model_json_schema()
            schema["output"]["properties"] = output_schema.get("properties", {})
            schema["output"]["required"] = output_schema.get("required", [])

    return schema


def langgraph_init_middleware(*args: Any, **kwargs: Any) -> Tuple[bool, Optional[str]]:
    """Middleware to check for langgraph.json and create uipath.json with schemas"""
    config = LangGraphConfig()

    if not config.exists:
        return True, None  # Continue with normal flow if no langgraph.json

    try:
        config.load_config()
        loaded_graphs = {}
        entrypoints = {}

        for graph in config.graphs:
            try:
                loaded_graph = graph.load_graph()
                loaded_graphs[graph.name] = loaded_graph

                graph_schema = generate_schema_from_graph(loaded_graph)
                entrypoints[graph.name] = {
                    "input": graph_schema["input"],
                    "output": graph_schema["output"],
                }

            except Exception as e:
                return False, f"Failed to load graph '{graph.name}': {str(e)}"

        uipath_config = {"type": "agent", "entrypoints": entrypoints}

        with open("uipath.json", "w") as f:
            json.dump(uipath_config, f, indent=2)

        return (
            False,
            f"Created uipath.json with schemas for {len(loaded_graphs)} graphs",
        )

    except Exception as e:
        return False, f"Error processing langgraph configuration: {str(e)}"


Middlewares.register("init", langgraph_init_middleware)


def handle_init():
    pass
