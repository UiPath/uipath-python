import json
import logging
from typing import List, Optional

from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.runnables.config import RunnableConfig
from langchain_core.tracers.langchain import wait_for_all_tracers
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph.state import CompiledStateGraph
from uipath_sdk._cli._runtime._contracts import (
    UiPathBaseRuntime,
    UiPathErrorCategory,
    UiPathRuntimeResult,
)

from ...tracers.tracer import Tracer
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

        self.validate()

        if self.context.state_graph is None:
            return None

        try:
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
                    tracer = Tracer()
                    tracer.init_trace(self.context.entrypoint, self.context.job_id)
                    callbacks = [tracer]

                graph_config: RunnableConfig = {
                    "configurable": {
                        "thread_id": self.context.job_id
                        if self.context.job_id
                        else "default"
                    },
                    "callbacks": callbacks,
                }

                # Execute the graph
                self.context.output = await graph.ainvoke(processed_input, graph_config)

                # Get the state if available
                try:
                    self.context.state = await graph.aget_state(graph_config)
                except Exception:
                    pass

                if self.context.langsmith_tracing_enabled:
                    wait_for_all_tracers()

                output_processor = LangGraphOutputProcessor(context=self.context)

                self.context.result = await output_processor.process()

                return self.context.result

        except Exception as e:
            if isinstance(e, LangGraphRuntimeError):
                raise

            raise LangGraphRuntimeError(
                "EXECUTION_ERROR",
                "Graph execution failed",
                f"Error: {str(e)}",
                UiPathErrorCategory.SYSTEM,
            ) from e

    def validate(self) -> None:
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
        graph_config = self.context.langgraph_config.get_graph(self.context.entrypoint)
        if not graph_config:
            raise LangGraphRuntimeError(
                "GRAPH_NOT_FOUND",
                "Graph not found",
                f"Graph '{self.context.entrypoint}' not found.",
                UiPathErrorCategory.DEPLOYMENT,
            )
        try:
            loaded_graph = graph_config.load_graph()
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
