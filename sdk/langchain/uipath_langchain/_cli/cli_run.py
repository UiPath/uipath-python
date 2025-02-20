import asyncio
import json
import logging
import sys
from os import environ as env
from typing import Any, Dict, Optional, Tuple

from dotenv import load_dotenv
from langchain_core.runnables.config import RunnableConfig
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command, Interrupt, StateSnapshot
from uipath_sdk._cli.middlewares import MiddlewareResult  # type: ignore

from ..tracers import Tracer
from ._utils._graph import LangGraphConfig

logger = logging.getLogger(__name__)
load_dotenv()

tracer = Tracer()


def get_interrupt_data(
    state: Optional[StateSnapshot],
) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """Check if the graph execution was interrupted."""
    if not state:
        return False, None

    if not hasattr(state, "next") or not state.next:
        return False, None

    for task in state.tasks:
        if hasattr(task, "interrupts") and task.interrupts:
            for interrupt in task.interrupts:
                if isinstance(interrupt, Interrupt):
                    return True, interrupt.value

    return False, None


async def execute(
    builder: StateGraph,
    input_data: Any,
    config: Optional[RunnableConfig] = None,
    resume: bool = False,
) -> None:
    """Execute the loaded graph with the given input."""

    async with AsyncSqliteSaver.from_conn_string("uipath.db") as memory:
        graph = builder.compile(checkpointer=memory)

        config = config or None

        if resume:
            result = await graph.ainvoke(Command(resume=input_data), config)
        else:
            result = await graph.ainvoke(input_data, config)

        state = None
        try:
            if config is None:
                raise Exception("Config is None")

            state = await graph.aget_state(config)
        except Exception as e:
            logger.error(f"[Executor]: Failed to get state: {str(e)}")

        is_interrupted, interrupt_data = get_interrupt_data(state)

        if is_interrupted:
            logger.info(f"[Executor] Graph execution interrupted: {interrupt_data}")
        else:
            logger.info("[Executor] Graph execution completed successfully")

        if hasattr(result, "dict"):
            serialized_result = result.dict()
        elif hasattr(result, "to_dict"):
            serialized_result = result.to_dict()
        else:
            serialized_result = dict(result)

        print(f"[OutputStart]{json.dumps(serialized_result)}[OutputEnd]")

        if interrupt_data:
            print(f"[SuspendStart]{json.dumps(interrupt_data)}[SuspendEnd]")

        if is_interrupted:
            sys.exit(42)


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
        tracer.init_trace(env.get("UIPATH_PROCESS_NAME"), env.get("UIPATH_JOB_KEY"))

        graph_config: RunnableConfig = {
            "configurable": {"thread_id": env.get("UIPATH_JOB_KEY", "default")},
            "callbacks": [],
        }

        asyncio.run(execute(state_graph, input_data, graph_config, resume))

        # Successful execution with no errors
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
