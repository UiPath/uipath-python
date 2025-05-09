import json
import logging
import os
from typing import List, Optional

from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.runnables.config import RunnableConfig
from langchain_core.tracers.langchain import wait_for_all_tracers
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.errors import EmptyInputError, GraphRecursionError, InvalidUpdateError
from langgraph.graph.state import CompiledStateGraph
from uipath._cli._runtime._contracts import (
    UiPathBaseRuntime,
    UiPathErrorCategory,
    UiPathRuntimeResult,
)

from ..._utils import _instrument_traceable_attributes
from ...tracers import AsyncUiPathTracer
from ._context import LangGraphRuntimeContext
from ._exception import LangGraphRuntimeError
from ._input import LangGraphInputProcessor
from ._output import LangGraphOutputProcessor

logger = logging.getLogger(__name__)


class LangGraphRuntime(UiPathBaseRuntime):
    """
    A runtime class implementing the async context manager protocol.
    This allows using the class with 'async with' statements.
    """

    def __init__(self, context: LangGraphRuntimeContext):
        super().__init__(context)
        self.context: LangGraphRuntimeContext = context

    async def execute(self) -> Optional[UiPathRuntimeResult]:
        """
        Execute the graph with the provided input and configuration.

        Returns:
            Dictionary with execution results

        Raises:
            LangGraphRuntimeError: If execution fails
        """
        _instrument_traceable_attributes()

        await self.validate()

        if self.context.state_graph is None:
            return None

        tracer = None

        try:
            if self.context.resume is False and self.context.job_id is None:
                # Delete the previous graph state file at debug time
                if os.path.exists(self.state_file_path):
                    os.remove(self.state_file_path)

            async with AsyncSqliteSaver.from_conn_string(
                self.state_file_path
            ) as memory:
                self.context.memory = memory

                # Compile the graph with the checkpointer
                graph = self.context.state_graph.compile(
                    checkpointer=self.context.memory
                )

                # Process input, handling resume if needed
                input_processor = LangGraphInputProcessor(context=self.context)

                processed_input = await input_processor.process()

                # Set up tracing if available
                callbacks: List[BaseCallbackHandler] = []

                if self.context.job_id and self.context.tracing_enabled:
                    tracer = AsyncUiPathTracer(context=self.context.trace_context)
                    callbacks = [tracer]

                graph_config: RunnableConfig = {
                    "configurable": {
                        "thread_id": self.context.job_id
                        if self.context.job_id
                        else "default"
                    },
                    "callbacks": callbacks,
                }

                recursion_limit = os.environ.get("LANGCHAIN_RECURSION_LIMIT", None)
                max_concurrency = os.environ.get("LANGCHAIN_MAX_CONCURRENCY", None)

                if recursion_limit is not None:
                    graph_config["recursion_limit"] = int(recursion_limit)
                if max_concurrency is not None:
                    graph_config["max_concurrency"] = int(max_concurrency)

                # Stream the output at debug time
                if self.context.job_id is None:
                    # Get final chunk while streaming
                    final_chunk = None
                    async for chunk in graph.astream(
                        processed_input,
                        graph_config,
                        stream_mode="values",
                        subgraphs=True,
                    ):
                        logger.info("%s", chunk)
                        final_chunk = chunk

                    # Extract data from the subgraph tuple format (namespace, data)
                    if isinstance(final_chunk, tuple) and len(final_chunk) == 2:
                        final_chunk = final_chunk[1]

                    # Process the final chunk to match ainvoke's output format
                    if isinstance(final_chunk, dict) and hasattr(
                        graph, "output_channels"
                    ):
                        output_channels = graph.output_channels

                        # Case 1: Single output channel as string
                        if (
                            isinstance(output_channels, str)
                            and output_channels in final_chunk
                        ):
                            self.context.output = final_chunk[output_channels]

                        # Case 2: Sequence of output channels
                        elif hasattr(output_channels, "__iter__") and not isinstance(
                            output_channels, str
                        ):
                            # Check if all channels are present in the chunk
                            if all(ch in final_chunk for ch in output_channels):
                                result = {}
                                for channel in output_channels:
                                    result[channel] = final_chunk[channel]
                                self.context.output = result
                            else:
                                # Fallback if not all channels are present
                                self.context.output = final_chunk
                    else:
                        # Use the whole chunk as output if we can't determine output channels
                        self.context.output = final_chunk
                else:
                    # Execute the graph normally at runtime
                    self.context.output = await graph.ainvoke(
                        processed_input, graph_config
                    )

                # Get the state if available
                try:
                    self.context.state = await graph.aget_state(graph_config)
                except Exception:
                    pass

                output_processor = LangGraphOutputProcessor(context=self.context)

                self.context.result = await output_processor.process()

                return self.context.result

        except Exception as e:
            if isinstance(e, LangGraphRuntimeError):
                raise

            detail = f"Error: {str(e)}"

            if isinstance(e, GraphRecursionError):
                raise LangGraphRuntimeError(
                    "GRAPH_RECURSION_ERROR",
                    "Graph recursion limit exceeded",
                    detail,
                    UiPathErrorCategory.USER,
                ) from e

            if isinstance(e, InvalidUpdateError):
                raise LangGraphRuntimeError(
                    "GRAPH_INVALID_UPDATE",
                    str(e),
                    detail,
                    UiPathErrorCategory.USER,
                ) from e

            if isinstance(e, EmptyInputError):
                raise LangGraphRuntimeError(
                    "GRAPH_EMPTY_INPUT",
                    "The input data is empty",
                    detail,
                    UiPathErrorCategory.USER,
                ) from e

            raise LangGraphRuntimeError(
                "EXECUTION_ERROR",
                "Graph execution failed",
                detail,
                UiPathErrorCategory.USER,
            ) from e
        finally:
            if tracer is not None:
                await tracer.wait_for_all_tracers()

            if self.context.langsmith_tracing_enabled:
                wait_for_all_tracers()

    async def validate(self) -> None:
        """Validate runtime inputs."""
        """Load and validate the graph configuration ."""
        try:
            if self.context.input:
                self.context.input_json = json.loads(self.context.input)
        except json.JSONDecodeError as e:
            raise LangGraphRuntimeError(
                "INPUT_INVALID_JSON",
                "Invalid JSON input",
                "The input data is not valid JSON.",
                UiPathErrorCategory.USER,
            ) from e

        if self.context.langgraph_config is None:
            raise LangGraphRuntimeError(
                "CONFIG_MISSING",
                "Invalid configuration",
                "Failed to load configuration",
                UiPathErrorCategory.DEPLOYMENT,
            )

        try:
            self.context.langgraph_config.load_config()
        except Exception as e:
            raise LangGraphRuntimeError(
                "CONFIG_INVALID",
                "Invalid configuration",
                f"Failed to load configuration: {str(e)}",
                UiPathErrorCategory.DEPLOYMENT,
            ) from e

        # Determine entrypoint if not provided
        graphs = self.context.langgraph_config.graphs
        if not self.context.entrypoint and len(graphs) == 1:
            self.context.entrypoint = graphs[0].name
        elif not self.context.entrypoint:
            graph_names = ", ".join(g.name for g in graphs)
            raise LangGraphRuntimeError(
                "ENTRYPOINT_MISSING",
                "Entrypoint required",
                f"Multiple graphs available. Please specify one of: {graph_names}.",
                UiPathErrorCategory.DEPLOYMENT,
            )

        # Get the specified graph
        self.graph_config = self.context.langgraph_config.get_graph(
            self.context.entrypoint
        )
        if not self.graph_config:
            raise LangGraphRuntimeError(
                "GRAPH_NOT_FOUND",
                "Graph not found",
                f"Graph '{self.context.entrypoint}' not found.",
                UiPathErrorCategory.DEPLOYMENT,
            )
        try:
            loaded_graph = await self.graph_config.load_graph()
            self.context.state_graph = (
                loaded_graph.builder
                if isinstance(loaded_graph, CompiledStateGraph)
                else loaded_graph
            )
        except ImportError as e:
            raise LangGraphRuntimeError(
                "GRAPH_IMPORT_ERROR",
                "Graph import failed",
                f"Failed to import graph '{self.context.entrypoint}': {str(e)}",
                UiPathErrorCategory.USER,
            ) from e
        except TypeError as e:
            raise LangGraphRuntimeError(
                "GRAPH_TYPE_ERROR",
                "Invalid graph type",
                f"Graph '{self.context.entrypoint}' is not a valid StateGraph or CompiledStateGraph: {str(e)}",
                UiPathErrorCategory.USER,
            ) from e
        except ValueError as e:
            raise LangGraphRuntimeError(
                "GRAPH_VALUE_ERROR",
                "Invalid graph value",
                f"Invalid value in graph '{self.context.entrypoint}': {str(e)}",
                UiPathErrorCategory.USER,
            ) from e
        except Exception as e:
            raise LangGraphRuntimeError(
                "GRAPH_LOAD_ERROR",
                "Failed to load graph",
                f"Unexpected error loading graph '{self.context.entrypoint}': {str(e)}",
                UiPathErrorCategory.USER,
            ) from e

    async def cleanup(self):
        if hasattr(self, "graph_config") and self.graph_config:
            await self.graph_config.cleanup()
