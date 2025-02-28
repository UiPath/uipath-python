import asyncio
import json
import logging
import os
from os import environ as env
from typing import Any, List, Optional

from dotenv import load_dotenv
from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.runnables.config import RunnableConfig
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph
from uipath_sdk._cli.middlewares import MiddlewareResult

from ..tracers import Tracer
from ._utils._graph import LangGraphConfig
from ._utils._input import GraphInput
from ._utils._output import GraphOutput

logger = logging.getLogger(__name__)
load_dotenv()


async def execute(
    builder: StateGraph,
    input_data: Any,
    config: RunnableConfig,
    resume: bool = False,
) -> None:
    """Execute the loaded graph with the given input."""

    async with AsyncSqliteSaver.from_conn_string("uipath.db") as memory:
        graph = builder.compile(checkpointer=memory)

        input = GraphInput(checkpointer=memory)
        retrieved_input = await input.retrieve(input_data, resume)

        result = await graph.ainvoke(retrieved_input, config)

        try:
            state = await graph.aget_state(config)
        except Exception as e:
            logger.error(f"[Executor]: Failed to get state: {str(e)}")
            state = None

        output = GraphOutput(result=result, state=state, checkpointer=memory)

        if output.interrupt_info:
            logger.info("[Executor]: Graph execution suspended.")
            await output.store_resume_trigger()
        else:
            logger.info("[Executor]: Graph execution completed successfully.")

        output.write_to_file()
        output.print_output()


def langgraph_run_middleware(
    entrypoint: Optional[str], input: Optional[str], resume: bool
) -> MiddlewareResult:
    """Middleware to handle langgraph execution"""
    config = LangGraphConfig()
    if not config.exists:
        return MiddlewareResult(
            should_continue=True
        )  # Continue with normal flow if no langgraph.json

    try:
        if input is None:
            raise Exception("Input is None")

        for key, value in os.environ.items():
            print(f"[Env]{key}={value}")
        print(f"[Input]: {input}")
        print(f"[Resumed]: {resume}")

        input_data = json.loads(input)

        if not entrypoint and len(config.graphs) == 1:
            entrypoint = config.graphs[0].name
        elif not entrypoint:
            return MiddlewareResult(
                should_continue=False,
                error_message=f"Multiple graphs available. Please specify one of: {', '.join(g.name for g in config.graphs)}.",
            )

        graph = config.get_graph(entrypoint)
        if not graph:
            return MiddlewareResult(
                should_continue=False, error_message=f"Graph '{entrypoint}' not found."
            )

        loaded_graph = graph.load_graph()
        state_graph = (
            loaded_graph.builder
            if isinstance(loaded_graph, CompiledStateGraph)
            else loaded_graph
        )
        # manually create a single trace for the job or else langgraph will create multiple parents on Interrrupts
        # parent the trace to the JobKey
        job_key = env.get("UIPATH_JOB_KEY", None)
        tracing_enabled = env.get("UIPATH_TRACING_ENABLED", True)
        callbacks: List[BaseCallbackHandler] = []
        run_name = env.get("PROCESS_KEY") or "default"

        if job_key and tracing_enabled:
            tracer = Tracer()
            tracer.init_trace(run_name, job_key)
            callbacks = [tracer]

        graph_config: RunnableConfig = {
            "configurable": {"thread_id": job_key if job_key else "default"},
            "callbacks": callbacks,
        }

        asyncio.run(execute(state_graph, input_data, graph_config, resume))

        return MiddlewareResult(should_continue=False, error_message=None)

    except json.JSONDecodeError:
        return MiddlewareResult(
            should_continue=False, error_message="Error: Invalid JSON input data."
        )
    except Exception as e:
        return MiddlewareResult(
            should_continue=False,
            error_message=f"Error: {str(e)}",
            should_include_stacktrace=True,
        )
