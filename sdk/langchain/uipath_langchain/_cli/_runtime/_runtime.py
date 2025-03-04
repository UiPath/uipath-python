import json
from typing import List, Optional

from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.runnables.config import RunnableConfig
from langchain_core.tracers.langchain import wait_for_all_tracers
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph.state import CompiledStateGraph
from uipath_sdk._cli._runtime._contracts import (
    ErrorCategory,
    ErrorInfo,
    ExecutionResult,
    RuntimeStatus,
)

from ...tracers.tracer import Tracer
from ._context import LangGraphRuntimeContext
from ._exception import LangGraphRuntimeError
from ._input import LangGraphInputProcessor
from ._output import LangGraphOutputProcessor


class LangGraphRuntime:
    """
    A runtime class implementing the async context manager protocol.
    This allows using the class with 'async with' statements.
    """

    def __init__(self, context: LangGraphRuntimeContext):
        self.context = context

    @classmethod
    def from_context(cls, context: LangGraphRuntimeContext):
        """
        Factory method to create a runtime instance from a context.

        Args:
            context: The runtime context with configuration

        Returns:
            An initialized LangGraphRuntime instance
        """
        runtime = cls(context)
        return runtime

    async def __aenter__(self):
        """
        Async enter method called when entering the 'async with' block.
        Initializes and prepares the runtime environment.

        Returns:
            The runtime instance
        """
        print(f"Starting runtime with job id: {self.context.job_id}")

        return self

    async def execute(self) -> Optional[ExecutionResult]:
        """
        Execute the graph with the provided input and configuration.

        Returns:
            Dictionary with execution results

        Raises:
            LangGraphRuntimeError: If execution fails
        """

        self._validate_context()

        if self.context.state_graph is None:
            return None

        try:
            async with AsyncSqliteSaver.from_conn_string(
                self.context.db_path
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
                ErrorCategory.SYSTEM,
            ) from e

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Async exit method called when exiting the 'async with' block.
        Cleans up resources and handles any exceptions.

        Always writes output file regardless of whether execution was successful,
        suspended, or encountered an error.
        """
        try:
            print(f"Shutting down runtime with job id: {self.context.job_id}")

            if self.context.result is None:
                execution_result = ExecutionResult()
            else:
                execution_result = self.context.result

            if exc_type:
                # Create error info from exception
                if isinstance(exc_val, LangGraphRuntimeError):
                    error_info = exc_val.error_info
                else:
                    # Generic error
                    error_info = ErrorInfo(
                        code=f"ERROR_{exc_type.__name__}",
                        title=f"Runtime error: {exc_type.__name__}",
                        detail=str(exc_val),
                        category=ErrorCategory.UNKNOWN,
                    )

                execution_result.status = RuntimeStatus.FAULTED
                execution_result.error = error_info

            content = execution_result.to_dict()
            print(content)

            # Always write output file
            with open(self.context.output_file, "w") as f:
                json.dump(content, f, indent=2, default=str)

            # Don't suppress exceptions
            return False

        except Exception as e:
            print(f"Error during runtime shutdown: {str(e)}")

            # Create a fallback error result if we fail during cleanup
            if not isinstance(e, LangGraphRuntimeError):
                error_info = ErrorInfo(
                    code="RUNTIME_SHUTDOWN_ERROR",
                    title="Runtime shutdown failed",
                    detail=f"Error: {str(e)}",
                    category=ErrorCategory.SYSTEM,
                )
            else:
                error_info = e.error_info

            # Last-ditch effort to write error output
            try:
                error_result = ExecutionResult(
                    status=RuntimeStatus.FAULTED, error=error_info
                )

                with open(self.context.output_file, "w") as f:
                    json.dump(error_result.to_dict(), f, indent=2, default=str)
            except Exception as write_error:
                print(f"Failed to write error output file: {str(write_error)}")

            # Re-raise as LangGraphRuntimeError if it's not already
            if not isinstance(e, LangGraphRuntimeError):
                raise LangGraphRuntimeError(
                    error_info.code,
                    error_info.title,
                    error_info.detail,
                    error_info.category,
                ) from e
            raise

    def _validate_context(self):
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
                ErrorCategory.USER,
            ) from e

        if self.context.langgraph_config is None:
            raise LangGraphRuntimeError(
                "CONFIG_MISSING",
                "Invalid configuration",
                "Failed to load configuration",
                ErrorCategory.USER,
            )

        try:
            self.context.langgraph_config.load_config()
        except Exception as e:
            raise LangGraphRuntimeError(
                "CONFIG_INVALID",
                "Invalid configuration",
                f"Failed to load configuration: {str(e)}",
                ErrorCategory.USER,
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
                ErrorCategory.USER,
            )

        # Get the specified graph
        graph_config = self.context.langgraph_config.get_graph(self.context.entrypoint)
        if not graph_config:
            raise LangGraphRuntimeError(
                "GRAPH_NOT_FOUND",
                "Graph not found",
                f"Graph '{self.context.entrypoint}' not found.",
                ErrorCategory.USER,
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
                ErrorCategory.USER,
            ) from e
        except TypeError as e:
            raise LangGraphRuntimeError(
                "GRAPH_TYPE_ERROR",
                "Invalid graph type",
                f"Graph '{self.context.entrypoint}' is not a valid StateGraph or CompiledStateGraph: {str(e)}",
                ErrorCategory.USER,
            ) from e
        except ValueError as e:
            raise LangGraphRuntimeError(
                "GRAPH_VALUE_ERROR",
                "Invalid graph value",
                f"Invalid value in graph '{self.context.entrypoint}': {str(e)}",
                ErrorCategory.USER,
            ) from e
        except Exception as e:
            raise LangGraphRuntimeError(
                "GRAPH_LOAD_ERROR",
                "Failed to load graph",
                f"Unexpected error loading graph '{self.context.entrypoint}': {str(e)}",
                ErrorCategory.USER,
            ) from e
