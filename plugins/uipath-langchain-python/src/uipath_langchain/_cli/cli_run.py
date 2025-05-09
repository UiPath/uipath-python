import asyncio
from os import environ as env
from typing import Optional

from dotenv import load_dotenv
from uipath._cli._runtime._contracts import UiPathTraceContext
from uipath._cli.middlewares import MiddlewareResult

from ._runtime._context import LangGraphRuntimeContext
from ._runtime._exception import LangGraphRuntimeError
from ._runtime._runtime import LangGraphRuntime
from ._utils._graph import LangGraphConfig

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
            context = LangGraphRuntimeContext.from_config(
                env.get("UIPATH_CONFIG_PATH", "uipath.json")
            )

            context.entrypoint = entrypoint
            context.input = input
            context.resume = resume
            context.langgraph_config = config
            context.logs_min_level = env.get("LOG_LEVEL", "INFO")
            context.job_id = env.get("UIPATH_JOB_KEY")
            context.trace_id = env.get("UIPATH_TRACE_ID")
            context.tracing_enabled = env.get("UIPATH_TRACING_ENABLED", True)
            context.trace_context = UiPathTraceContext(
                enabled=env.get("UIPATH_TRACING_ENABLED", True),
                trace_id=env.get("UIPATH_TRACE_ID"),
                parent_span_id=env.get("UIPATH_PARENT_SPAN_ID"),
                root_span_id=env.get("UIPATH_ROOT_SPAN_ID"),
                job_id=env.get("UIPATH_JOB_KEY"),
                org_id=env.get("UIPATH_ORGANIZATION_ID"),
                tenant_id=env.get("UIPATH_TENANT_ID"),
                process_key=env.get("UIPATH_PROCESS_UUID"),
                folder_key=env.get("UIPATH_FOLDER_KEY"),
            )
            context.langsmith_tracing_enabled = env.get("LANGSMITH_TRACING", False)

            # Add default env variables
            env["UIPATH_REQUESTING_PRODUCT"] = "uipath-python-sdk"
            env["UIPATH_REQUESTING_FEATURE"] = "langgraph-agent"

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
