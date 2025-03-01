import asyncio
import logging
from os import environ as env
from typing import Optional

from dotenv import load_dotenv
from uipath_sdk._cli.middlewares import MiddlewareResult

from ._runtime._context import LangGraphRuntimeContext
from ._runtime._exception import LangGraphRuntimeError
from ._runtime._runtime import LangGraphRuntime
from ._utils._graph import LangGraphConfig

logger = logging.getLogger(__name__)
load_dotenv()


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

        async def execute():
            context = LangGraphRuntimeContext(
                entrypoint=entrypoint,
                input=input,
                job_id=env.get("UIPATH_JOB_KEY"),
                trace_id=env.get("UIPATH_TRACE_ID"),
                tracing_enabled=env.get("UIPATH_TRACING_ENABLED", True),
                langsmith_tracing_enabled=env.get("LANGSMITH_TRACING", False),
                resume=resume,
                langgraph_config=config,
            )

            async with LangGraphRuntime.from_context(context) as runtime:
                await runtime.execute()

        asyncio.run(execute())

        return MiddlewareResult(should_continue=False, error_message=None)

    except LangGraphRuntimeError as e:
        return MiddlewareResult(
            should_continue=False,
            error_message=e.error_info.detail,
            should_include_stacktrace=True,
        )
    except Exception as e:
        return MiddlewareResult(
            should_continue=False,
            error_message=f"Error: {str(e)}",
            should_include_stacktrace=True,
        )
