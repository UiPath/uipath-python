import asyncio
import json
import os
import uuid
from typing import Any, Dict

from langgraph.graph.state import CompiledStateGraph
from uipath_sdk._cli._utils._parse_ast import generate_bindings_json  # type: ignore
from uipath_sdk._cli.middlewares import MiddlewareResult

from ._utils._graph import LangGraphConfig


def resolve_refs(schema, root=None):
    """Recursively resolves $ref references in a JSON schema."""
    if root is None:
        root = schema  # Store the root schema to resolve $refs

    if isinstance(schema, dict):
        if "$ref" in schema:
            ref_path = schema["$ref"].lstrip("#/").split("/")
            ref_schema = root
            for part in ref_path:
                ref_schema = ref_schema.get(part, {})
            return resolve_refs(ref_schema, root)

        return {k: resolve_refs(v, root) for k, v in schema.items()}

    elif isinstance(schema, list):
        return [resolve_refs(item, root) for item in schema]

    return schema


def generate_schema_from_graph(graph: CompiledStateGraph) -> Dict[str, Any]:
    """Extract input/output schema from a LangGraph graph"""
    schema = {
        "input": {"type": "object", "properties": {}, "required": []},
        "output": {"type": "object", "properties": {}, "required": []},
    }

    if hasattr(graph, "input_schema"):
        if hasattr(graph.input_schema, "model_json_schema"):
            input_schema = graph.input_schema.model_json_schema()

            unpacked_ref_def_properties = resolve_refs(input_schema)

            schema["input"]["properties"] = unpacked_ref_def_properties.get(
                "properties", {}
            )
            schema["input"]["required"] = unpacked_ref_def_properties.get(
                "required", []
            )

    if hasattr(graph, "output_schema"):
        if hasattr(graph.output_schema, "model_json_schema"):
            output_schema = graph.output_schema.model_json_schema()

            unpacked_ref_def_properties = resolve_refs(output_schema)
            schema["output"]["properties"] = unpacked_ref_def_properties.get(
                "properties", {}
            )
            schema["output"]["required"] = unpacked_ref_def_properties.get(
                "required", []
            )

    return schema


async def langgraph_init_middleware_async(entrypoint: str) -> MiddlewareResult:
    """Middleware to check for langgraph.json and create uipath.json with schemas"""
    config = LangGraphConfig()
    if not config.exists:
        return MiddlewareResult(
            should_continue=True
        )  # Continue with normal flow if no langgraph.json

    try:
        config.load_config()
        entrypoints = []
        all_bindings = {"version": "2.0", "resources": []}
        mermaids = {}

        for graph in config.graphs:
            if entrypoint and graph.name != entrypoint:
                continue

            try:
                loaded_graph = await graph.load_graph()
                state_graph = (
                    loaded_graph.builder
                    if isinstance(loaded_graph, CompiledStateGraph)
                    else loaded_graph
                )
                compiled_graph = state_graph.compile()
                graph_schema = generate_schema_from_graph(compiled_graph)

                mermaids[graph.name] = compiled_graph.get_graph(xray=1).draw_mermaid()

                try:
                    print("Generating bindings for ", graph.file_path)
                    # Make sure the file path exists
                    if os.path.exists(graph.file_path):
                        file_bindings = generate_bindings_json(graph.file_path)

                        # Merge bindings
                        if "resources" in file_bindings:
                            all_bindings["resources"] = file_bindings["resources"]
                except Exception as e:
                    print(
                        f"Warning: Could not generate bindings for {graph.file_path}: {str(e)}"
                    )

                new_entrypoint: dict[str, Any] = {
                    "filePath": graph.name,
                    "uniqueId": str(uuid.uuid4()),
                    "type": "agent",
                    "input": graph_schema["input"],
                    "output": graph_schema["output"],
                }
                entrypoints.append(new_entrypoint)

            except Exception as e:
                print(f"Error during graph load: {e}")
                return MiddlewareResult(
                    should_continue=False,
                    error_message=f"Failed to load graph '{graph.name}': {str(e)}",
                    should_include_stacktrace=True,
                )
            finally:
                await graph.cleanup()

        if entrypoint and not entrypoints:
            return MiddlewareResult(
                should_continue=False,
                error_message=f"Error: No graph found with name '{entrypoint}'",
            )

        uipath_config = {"entryPoints": entrypoints, "bindings": all_bindings}

        # Save the uipath.json file
        config_path = "uipath.json"
        with open(config_path, "w") as f:
            json.dump(uipath_config, f, indent=2)

        for graph_name, mermaid_content in mermaids.items():
            mermaid_file_path = f"{graph_name}.mermaid"
            try:
                with open(mermaid_file_path, "w") as f:
                    f.write(mermaid_content)
            except Exception as write_error:
                return MiddlewareResult(
                    should_continue=False,
                    error_message=f"Error writing mermaid file for '{graph_name}': {str(write_error)}",
                    should_include_stacktrace=True,
                )

        return MiddlewareResult(
            should_continue=False,
            info_message=f"Configuration file {config_path} created successfully.",
        )

    except Exception as e:
        return MiddlewareResult(
            should_continue=False,
            error_message=f"Error processing langgraph configuration: {str(e)}",
            should_include_stacktrace=True,
        )


def langgraph_init_middleware(entrypoint: str) -> MiddlewareResult:
    """Middleware to check for langgraph.json and create uipath.json with schemas"""
    return asyncio.run(langgraph_init_middleware_async(entrypoint))
