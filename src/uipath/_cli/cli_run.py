# type: ignore
import asyncio
import json
import os
from datetime import datetime
from os import environ as env
from typing import Optional, Sequence
import uuid

import click
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

from uipath._cli._runtime._runtime_factory import generate_runtime_factory
from uipath._cli._utils._common import read_resource_overwrites_from_file
from uipath._cli._utils._debug import setup_debugging
from uipath._utils._bindings import ResourceOverwritesContext
from uipath.tracing import JsonLinesFileExporter, LlmOpsHttpExporter
from uipath.tracing._utils import _SpanUtils

from .._utils.constants import (
    ENV_JOB_ID,
)
from ..telemetry import track
from ._runtime._contracts import UiPathRuntimeError
from ._utils._console import ConsoleLogger
from .middlewares import Middlewares

# Import LangChain instrumentor for automatic span generation
try:
    from openinference.instrumentation.langchain import (
        LangChainInstrumentor,
        get_current_span,
    )
    LANGCHAIN_INSTRUMENTATION_AVAILABLE = True
except ImportError:
    LANGCHAIN_INSTRUMENTATION_AVAILABLE = False

console = ConsoleLogger()


class MemorySpanExporter(SpanExporter):
    """Span exporter that collects spans in memory for later processing."""

    def __init__(self):
        self.spans = []

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        """Export spans to memory."""
        try:
            for span in spans:
                uipath_span = _SpanUtils.otel_span_to_uipath_span(
                    span, serialize_attributes=True
                )
                self.spans.append(uipath_span.to_dict(serialize_attributes=False))
            return SpanExportResult.SUCCESS
        except Exception:
            return SpanExportResult.FAILURE

    def shutdown(self) -> None:
        """Shutdown the exporter."""
        pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Force flush any buffered spans."""
        return True


def _generate_evaluation_set(
    input_data: str,
    output_data: str,
    entrypoint: str,
    eval_set_path: str,
    evaluators: list[str] = None,
    spans: list[dict] = None,
) -> None:
    """Generate an evaluation set JSON file from a run execution.

    Args:
        input_data: The input data used for the run (as JSON string)
        output_data: The output data from the run (as JSON string)
        entrypoint: Path to the agent script
        eval_set_path: Path where the evaluation set JSON file will be saved
        evaluators: List of evaluator names to use (e.g., ['json_similarity', 'exact_match'])
        spans: Optional list of span dictionaries containing node execution data
    """
    try:
        # Use json_similarity as default if no evaluators specified
        if not evaluators:
            evaluators = ["json_similarity"]

        # Create the directory structure for eval sets and evaluators
        eval_set_file = os.path.abspath(eval_set_path)
        eval_set_dir = os.path.dirname(eval_set_file)

        # If not already in an eval-sets dir, create proper structure
        if not eval_set_dir.endswith("eval-sets"):
            eval_set_dir = os.path.join(eval_set_dir, "evals", "eval-sets")
            eval_set_file = os.path.join(eval_set_dir, os.path.basename(eval_set_path))

        os.makedirs(eval_set_dir, exist_ok=True)

        # Create evaluators directory at the sibling level
        evaluators_dir = os.path.join(os.path.dirname(eval_set_dir), "evaluators")
        os.makedirs(evaluators_dir, exist_ok=True)
        # Parse input and output
        try:
            parsed_input = json.loads(input_data) if input_data else {}
        except (json.JSONDecodeError, TypeError):
            # If input_data is already a dict or not JSON, handle it
            if isinstance(input_data, dict):
                parsed_input = input_data
            else:
                parsed_input = {"raw_input": str(input_data)}

        try:
            # Handle output_data which might be a string, dict, or other object
            if isinstance(output_data, str):
                parsed_output = json.loads(output_data)
            elif isinstance(output_data, dict):
                parsed_output = output_data
            else:
                # For other types, try to convert to dict
                parsed_output = json.loads(str(output_data))
        except (json.JSONDecodeError, TypeError):
            parsed_output = {"raw_output": str(output_data)}

        # Generate unique IDs
        eval_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat() + "Z"

        # Build evaluation criteria and create evaluator files
        evaluation_criteria = {}
        evaluator_refs = []

        # Evaluator type mapping (supports both short names and full type IDs)
        evaluator_type_map = {
            "json_similarity": {
                "name": "JsonSimilarityEvaluator",
                "evaluatorTypeId": "uipath-json-similarity",
                "config_defaults": {"name": "JsonSimilarityEvaluator"}
            },
            "uipath-json-similarity": {
                "name": "JsonSimilarityEvaluator",
                "evaluatorTypeId": "uipath-json-similarity",
                "config_defaults": {"name": "JsonSimilarityEvaluator"}
            },
            "exact_match": {
                "name": "ExactMatchEvaluator",
                "evaluatorTypeId": "uipath-exact-match",
                "config_defaults": {"name": "ExactMatchEvaluator", "case_sensitive": False}
            },
            "uipath-exact-match": {
                "name": "ExactMatchEvaluator",
                "evaluatorTypeId": "uipath-exact-match",
                "config_defaults": {"name": "ExactMatchEvaluator", "case_sensitive": False}
            },
            "contains": {
                "name": "ContainsEvaluator",
                "evaluatorTypeId": "uipath-contains",
                "config_defaults": {"name": "ContainsEvaluator"}
            },
            "uipath-contains": {
                "name": "ContainsEvaluator",
                "evaluatorTypeId": "uipath-contains",
                "config_defaults": {"name": "ContainsEvaluator"}
            },
            "llm_judge": {
                "name": "LLMJudgeOutputEvaluator",
                "evaluatorTypeId": "uipath-llm-judge-output-semantic-similarity",
                "config_defaults": {"name": "LLMJudgeOutputEvaluator", "model": "anthropic.claude-3-5-sonnet-20240620-v1:0"}
            },
            "uipath-llm-judge-output-semantic-similarity": {
                "name": "LLMJudgeOutputEvaluator",
                "evaluatorTypeId": "uipath-llm-judge-output-semantic-similarity",
                "config_defaults": {"name": "LLMJudgeOutputEvaluator", "model": "anthropic.claude-3-5-sonnet-20240620-v1:0"}
            },
            "llm_judge_strict_json": {
                "name": "LLMJudgeStrictJSONSimilarityOutputEvaluator",
                "evaluatorTypeId": "uipath-llm-judge-output-strict-json-similarity",
                "config_defaults": {"name": "LLMJudgeStrictJSONSimilarityOutputEvaluator", "model": "anthropic.claude-3-5-sonnet-20240620-v1:0"}
            },
            "uipath-llm-judge-output-strict-json-similarity": {
                "name": "LLMJudgeStrictJSONSimilarityOutputEvaluator",
                "evaluatorTypeId": "uipath-llm-judge-output-strict-json-similarity",
                "config_defaults": {"name": "LLMJudgeStrictJSONSimilarityOutputEvaluator", "model": "anthropic.claude-3-5-sonnet-20240620-v1:0"}
            },
            "llm_judge_trajectory": {
                "name": "LLMJudgeTrajectoryEvaluator",
                "evaluatorTypeId": "uipath-llm-judge-trajectory",
                "config_defaults": {"name": "LLMJudgeTrajectoryEvaluator", "model": "anthropic.claude-3-5-sonnet-20240620-v1:0"}
            },
            "uipath-llm-judge-trajectory": {
                "name": "LLMJudgeTrajectoryEvaluator",
                "evaluatorTypeId": "uipath-llm-judge-trajectory",
                "config_defaults": {"name": "LLMJudgeTrajectoryEvaluator", "model": "anthropic.claude-3-5-sonnet-20240620-v1:0"}
            },
            "llm_judge_trajectory_simulation": {
                "name": "LLMJudgeTrajectorySimulationEvaluator",
                "evaluatorTypeId": "uipath-llm-judge-trajectory-simulation",
                "config_defaults": {"name": "LLMJudgeTrajectorySimulationEvaluator", "model": "anthropic.claude-3-5-sonnet-20240620-v1:0"}
            },
            "uipath-llm-judge-trajectory-simulation": {
                "name": "LLMJudgeTrajectorySimulationEvaluator",
                "evaluatorTypeId": "uipath-llm-judge-trajectory-simulation",
                "config_defaults": {"name": "LLMJudgeTrajectorySimulationEvaluator", "model": "anthropic.claude-3-5-sonnet-20240620-v1:0"}
            },
            "tool_call_args": {
                "name": "ToolCallArgsEvaluator",
                "evaluatorTypeId": "uipath-tool-call-args",
                "config_defaults": {"name": "ToolCallArgsEvaluator"}
            },
            "uipath-tool-call-args": {
                "name": "ToolCallArgsEvaluator",
                "evaluatorTypeId": "uipath-tool-call-args",
                "config_defaults": {"name": "ToolCallArgsEvaluator"}
            },
            "tool_call_count": {
                "name": "ToolCallCountEvaluator",
                "evaluatorTypeId": "uipath-tool-call-count",
                "config_defaults": {"name": "ToolCallCountEvaluator"}
            },
            "uipath-tool-call-count": {
                "name": "ToolCallCountEvaluator",
                "evaluatorTypeId": "uipath-tool-call-count",
                "config_defaults": {"name": "ToolCallCountEvaluator"}
            },
            "tool_call_order": {
                "name": "ToolCallOrderEvaluator",
                "evaluatorTypeId": "uipath-tool-call-order",
                "config_defaults": {"name": "ToolCallOrderEvaluator"}
            },
            "uipath-tool-call-order": {
                "name": "ToolCallOrderEvaluator",
                "evaluatorTypeId": "uipath-tool-call-order",
                "config_defaults": {"name": "ToolCallOrderEvaluator"}
            },
            "tool_call_output": {
                "name": "ToolCallOutputEvaluator",
                "evaluatorTypeId": "uipath-tool-call-output",
                "config_defaults": {"name": "ToolCallOutputEvaluator"}
            },
            "uipath-tool-call-output": {
                "name": "ToolCallOutputEvaluator",
                "evaluatorTypeId": "uipath-tool-call-output",
                "config_defaults": {"name": "ToolCallOutputEvaluator"}
            },
        }

        for evaluator_name in evaluators:
            if evaluator_name not in evaluator_type_map:
                console.warning(f"Unknown evaluator '{evaluator_name}', skipping")
                continue

            evaluator_info = evaluator_type_map[evaluator_name]
            evaluator_id = str(uuid.uuid4())
            evaluator_refs.append(evaluator_id)

            # Create evaluator JSON file
            evaluator_def = {
                "id": evaluator_id,
                "name": f"{evaluator_info['name']} (auto-generated)",
                "version": "1.0",
                "evaluatorTypeId": evaluator_info["evaluatorTypeId"],
                "evaluatorConfig": evaluator_info["config_defaults"],
            }

            evaluator_file = os.path.join(
                evaluators_dir, f"{evaluator_name}-{evaluator_id[:8]}.json"
            )
            with open(evaluator_file, "w") as f:
                json.dump(evaluator_def, f, indent=2)

            # Add evaluation criteria for this eval item (keyed by evaluator ID)
            evaluation_criteria[evaluator_id] = {
                "expected_output": parsed_output,
            }

        # Create evaluation items
        evaluation_items = []

        # If spans are provided, create per-node evaluations
        if spans:
            # Filter spans to only include workflow nodes
            node_spans = {}
            node_order = []  # Track order of nodes

            for span in spans:
                # First try to get the span name from the Name field (UiPath format)
                span_name = span.get('Name', span.get('name', ''))
                attributes = span.get('Attributes', span.get('attributes', {}))

                # Parse attributes if they're a JSON string
                if isinstance(attributes, str):
                    try:
                        attributes = json.loads(attributes)
                    except:
                        attributes = {}

                # Determine the node name from various possible sources
                node_name = None
                if isinstance(attributes, dict):
                    node_name = attributes.get('node_name', attributes.get('langgraph.node', None))

                # If no node_name attribute, use the span Name as the node name
                if not node_name and span_name:
                    node_name = span_name

                # Only include valid workflow nodes (exclude system nodes, internal components, and LLM calls)
                if node_name and node_name not in ['__start__', '__end__'] and not any(
                    node_name.startswith(prefix) for prefix in ['Runnable', 'UiPath', 'JsonOutput']
                ):
                    if node_name not in node_spans:
                        node_spans[node_name] = []
                        node_order.append(node_name)
                    node_spans[node_name].append(span)

            if node_spans:
                console.info(f"Found {len(node_spans)} workflow node(s) for evaluation generation")

                # Create evaluation for each node in execution order
                for node_name in node_order:
                    node_span_list = node_spans[node_name]
                    # Get the most recent span for this node
                    node_span = node_span_list[-1]
                    node_attributes = node_span.get('Attributes', node_span.get('attributes', {}))

                    # Parse attributes if they're a JSON string
                    if isinstance(node_attributes, str):
                        try:
                            node_attributes = json.loads(node_attributes)
                        except:
                            node_attributes = {}

                    # Try different output keys: output.value, output, outputs
                    node_output = node_attributes.get('output.value', node_attributes.get('output', node_attributes.get('outputs', None)))
                    if isinstance(node_output, str):
                        try:
                            node_output = json.loads(node_output)
                        except:
                            pass

                    if node_output:
                        # Create node-specific evaluation
                        node_eval_id = str(uuid.uuid4())
                        node_evaluation_criteria = {}

                        # Add evaluation criteria for each evaluator with node output
                        for evaluator_id in evaluator_refs:
                            node_evaluation_criteria[evaluator_id] = {
                                "expected_output": node_output,
                            }

                        evaluation_items.append({
                            "id": node_eval_id,
                            "name": f"Node: {node_name}",
                            "inputs": parsed_input,  # Use agent input, not node-specific input
                            "evaluationCriterias": node_evaluation_criteria,
                            "expectedAgentBehavior": f"The agent should execute node '{node_name}' and produce the expected output during the workflow execution.",
                            "nodeId": node_name,  # Add node identifier for evaluators to match against trace
                        })

        # Always include final output evaluation
        evaluation_item = {
            "id": eval_id,
            "name": f"Final Output",
            "inputs": parsed_input,
            "evaluationCriterias": evaluation_criteria,
            "expectedAgentBehavior": "Agent should produce the expected output for the given input",
        }
        evaluation_items.append(evaluation_item)

        # Create evaluation set
        eval_set = {
            "id": str(uuid.uuid4()),
            "name": f"Evaluation set generated from {entrypoint}",
            "version": "1.0",
            "evaluatorRefs": evaluator_refs,
            "evaluations": evaluation_items,
        }

        # Save eval set to file
        with open(eval_set_file, "w") as f:
            json.dump(eval_set, f, indent=2)

        console.success(f"Evaluation set generated and saved to: {eval_set_file}")
        console.info(f"Generated {len(evaluation_items)} evaluation(s) with {len(evaluator_refs)} evaluator(s) in: {evaluators_dir}")

    except Exception as e:
        console.error(f"Failed to generate evaluation set: {str(e)}", include_traceback=True)


@click.command()
@click.argument("entrypoint", required=False)
@click.argument("input", required=False, default="{}")
@click.option("--resume", is_flag=True, help="Resume execution from a previous state")
@click.option(
    "-f",
    "--file",
    required=False,
    type=click.Path(exists=True),
    help="File path for the .json input",
)
@click.option(
    "--input-file",
    required=False,
    type=click.Path(exists=True),
    help="Alias for '-f/--file' arguments",
)
@click.option(
    "--output-file",
    required=False,
    type=click.Path(),
    help="File path where the output will be written (will overwrite if exists)",
)
@click.option(
    "--trace-file",
    required=False,
    type=click.Path(exists=False),
    help="File path where the trace spans will be written (JSON Lines format)",
)
@click.option(
    "--debug",
    is_flag=True,
    help="Enable debugging with debugpy. The process will wait for a debugger to attach.",
)
@click.option(
    "--debug-port",
    type=int,
    default=5678,
    help="Port for the debug server (default: 5678)",
)
@click.option(
    "--generate-evals",
    required=False,
    type=click.Path(),
    help="Generate an evaluation set file from this run and save it to the specified path (will overwrite if exists)",
)
@click.option(
    "--eval-evaluators",
    multiple=True,
    default=["json_similarity"],
    help="Evaluators to use for generated eval set (can be specified multiple times). Available: json_similarity, exact_match, contains, llm_judge, llm_judge_strict_json, llm_judge_trajectory, llm_judge_trajectory_simulation, tool_call_args, tool_call_count, tool_call_order, tool_call_output. You can also use full type IDs like 'uipath-json-similarity'.",
)
@track(when=lambda *_a, **_kw: env.get(ENV_JOB_ID) is None)
def run(
    entrypoint: Optional[str],
    input: Optional[str],
    resume: bool,
    file: Optional[str],
    input_file: Optional[str],
    output_file: Optional[str],
    trace_file: Optional[str],
    debug: bool,
    debug_port: int,
    generate_evals: Optional[str],
    eval_evaluators: tuple[str],
) -> None:
    """Execute the project."""
    context_args = {
        "entrypoint": entrypoint,
        "input": input,
        "resume": resume,
        "input_file": file or input_file,
        "execution_output_file": output_file,
        "trace_file": trace_file,
        "debug": debug,
        "generate_evals": generate_evals,
        # Enable tracing if we're generating evals to capture node data
        "tracing_enabled": True if generate_evals else None,
    }
    input_file = file or input_file
    # Setup debugging if requested
    if not setup_debugging(debug, debug_port):
        console.error(f"Failed to start debug server on port {debug_port}")

    result = Middlewares.next(
        "run",
        entrypoint,
        input,
        resume,
        input_file=input_file,
        execution_output_file=output_file,
        trace_file=trace_file,
        debug=debug,
        debug_port=debug_port,
    )

    if result.error_message:
        console.error(result.error_message)

    if result.should_continue:
        if not entrypoint:
            console.error("""No entrypoint specified. Please provide a path to a Python script.
    Usage: `uipath run <entrypoint_path> <input_arguments> [-f <input_json_file_path>]`""")

        if not os.path.exists(entrypoint):
            console.error(f"""Script not found at path {entrypoint}.
    Usage: `uipath run <entrypoint_path> <input_arguments> [-f <input_json_file_path>]`""")

        try:
            execution_result = None
            memory_span_exporter = None

            async def execute() -> None:
                nonlocal execution_result, memory_span_exporter
                runtime_factory = generate_runtime_factory()
                context = runtime_factory.new_context(**context_args)
                if context.job_id:
                    runtime_factory.add_span_exporter(LlmOpsHttpExporter())

                if trace_file:
                    runtime_factory.add_span_exporter(JsonLinesFileExporter(trace_file))

                # Add memory span exporter if generating evals to capture node-level data
                # Use batch=False to ensure immediate export of spans
                if generate_evals:
                    memory_span_exporter = MemorySpanExporter()
                    runtime_factory.add_span_exporter(memory_span_exporter, batch=False)

                    # Add LangChain instrumentor to automatically trace LangChain/LangGraph operations
                    if LANGCHAIN_INSTRUMENTATION_AVAILABLE:
                        runtime_factory.add_instrumentor(LangChainInstrumentor, get_current_span)

                if context.job_id:
                    async with ResourceOverwritesContext(
                        lambda: read_resource_overwrites_from_file(context.runtime_dir)
                    ) as ctx:
                        console.info(
                            f"Applied {ctx.overwrites_count} resource overwrite(s)"
                        )

                        execution_result = await runtime_factory.execute(context)
                else:
                    execution_result = await runtime_factory.execute(context)

                if not context.job_id:
                    console.info(execution_result.output)

            asyncio.run(execute())

            # Generate evaluation set if requested
            if generate_evals and execution_result:
                # Get the actual input data (from file or argument)
                actual_input = input
                if input_file and os.path.exists(input_file):
                    try:
                        with open(input_file, 'r') as f:
                            actual_input = f.read()
                    except Exception as e:
                        console.warning(f"Failed to read input file for eval generation: {e}")

                # Convert output to proper format for eval generation
                output_for_eval = execution_result.output if hasattr(execution_result, 'output') else execution_result

                # If output is a Pydantic model, convert to dict
                if hasattr(output_for_eval, 'model_dump'):
                    output_for_eval = output_for_eval.model_dump()
                elif hasattr(output_for_eval, 'dict'):
                    output_for_eval = output_for_eval.dict()
                # If it's already a dict, ensure it's not wrapped
                elif isinstance(output_for_eval, dict) and 'dict' in output_for_eval:
                    # Unwrap if it's in the format {"dict": "..."}
                    try:
                        import ast
                        output_for_eval = ast.literal_eval(output_for_eval['dict'])
                    except:
                        pass  # Keep as-is if parsing fails

                # Get spans from memory exporter if available
                collected_spans = memory_span_exporter.spans if memory_span_exporter else None

                _generate_evaluation_set(
                    input_data=actual_input,
                    output_data=output_for_eval,
                    entrypoint=entrypoint,
                    eval_set_path=generate_evals,
                    evaluators=list(eval_evaluators) if eval_evaluators else None,
                    spans=collected_spans,
                )

        except UiPathRuntimeError as e:
            console.error(f"{e.error_info.title} - {e.error_info.detail}")
        except Exception as e:
            # Handle unexpected errors
            console.error(
                f"Error: Unexpected error occurred - {str(e)}", include_traceback=True
            )

    console.success("Successful execution.")


if __name__ == "__main__":
    run()
