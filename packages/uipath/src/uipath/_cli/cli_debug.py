import asyncio
import logging
from contextlib import AsyncExitStack
from typing import Any, cast, get_args

import click

from uipath._cli._chat._bridge import get_chat_bridge
from uipath._cli._debug._bridge import DebugAttachMode, get_debug_bridge
from uipath._cli._utils._debug import setup_debugging
from uipath._cli._utils._studio_project import StudioClient
from uipath._cli._utils._tracing import create_trace_manager
from uipath.eval.mocks import UiPathMockRuntime
from uipath.eval.mocks._mock_runtime import load_simulation_config
from uipath.platform import UiPath
from uipath.platform.common import (
    ExecutionSourceContext,
    ResourceOverwritesContext,
    UiPathConfig,
)
from uipath.runtime import (
    ConversationalWorkspaceRuntime,
    HydrationRuntime,
    UiPathExecuteOptions,
    UiPathRuntimeContext,
    UiPathRuntimeFactoryProtocol,
    UiPathRuntimeFactoryRegistry,
    UiPathRuntimeProtocol,
    Workspace,
    WorkspaceHydrator,
    WorkspaceRegistryStore,
)
from uipath.runtime.chat import UiPathChatProtocol, UiPathChatRuntime
from uipath.runtime.debug import UiPathDebugProtocol, UiPathDebugRuntime
from uipath.tracing import LiveTrackingSpanProcessor, LlmOpsHttpExporter

from ._governance_bootstrap import GovernanceBootstrap, resolve_governance
from ._telemetry import track_command
from ._utils._console import ConsoleLogger
from .middlewares import Middlewares

console = ConsoleLogger()
logger = logging.getLogger(__name__)


@click.command()
@click.argument("entrypoint", required=False)
@click.argument("input", required=False, default=None)
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
    type=click.Path(exists=False),
    help="File path where the output will be written",
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
    "--attach",
    type=click.Choice(list(get_args(DebugAttachMode)), case_sensitive=False),
    default=None,
    help=(
        "Debugger attach mode. Defaults to 'signalr' for cloud runs, "
        "'console' for local runs."
    ),
)
@track_command("debug")
def debug(
    entrypoint: str | None,
    input: str | None,
    resume: bool,
    file: str | None,
    input_file: str | None,
    output_file: str | None,
    debug: bool,
    debug_port: int,
    attach: str | None,
) -> None:
    """Debug the project."""
    input_file = file or input_file
    # Setup debugging if requested
    if not setup_debugging(debug, debug_port):
        console.error(f"Failed to start debug server on port {debug_port}")

    attach_mode: DebugAttachMode | None = (
        cast(DebugAttachMode, attach.lower()) if attach else None
    )

    result = Middlewares.next(
        "debug",
        entrypoint,
        input,
        resume,
        input_file=input_file,
        output_file=output_file,
        debug=debug,
        debug_port=debug_port,
        attach=attach_mode,
    )

    if result.error_message:
        console.error(result.error_message)

    if result.should_continue:
        if not entrypoint:
            console.error("""No entrypoint specified.
    Usage: `uipath debug <entrypoint> <input_arguments> [-f <input_json_file_path>]`""")
            return

        try:

            async def execute_debug_runtime():
                trace_manager = create_trace_manager()

                ctx = UiPathRuntimeContext.with_defaults(
                    input=input,
                    input_file=input_file,
                    output_file=output_file,
                    resume=resume,
                    trace_manager=trace_manager,
                    command="debug",
                )
                with ExecutionSourceContext(ctx.execution_source), ctx:
                    factory: UiPathRuntimeFactoryProtocol | None = None
                    governance_bootstrap: GovernanceBootstrap | None = None

                    try:
                        trigger_poll_interval: float = 5.0

                        factory = UiPathRuntimeFactoryRegistry.get(context=ctx)
                        factory_settings = await factory.get_settings()
                        trace_settings = (
                            factory_settings.trace_settings
                            if factory_settings
                            else None
                        )
                        agent_type = (
                            factory_settings.agent_type if factory_settings else None
                        )
                        agent_framework = (
                            factory_settings.agent_framework
                            if factory_settings
                            else None
                        )
                        governance_bootstrap = await resolve_governance(
                            agent_framework=agent_framework,
                            agent_type=agent_type,
                            is_conversational=ctx.conversation_id is not None,
                        )
                        governance_runtime_id = (
                            ctx.conversation_id or ctx.job_id or "default"
                        )

                        if ctx.job_id:
                            if UiPathConfig.is_tracing_enabled:
                                trace_manager.add_span_processor(
                                    LiveTrackingSpanProcessor(
                                        LlmOpsHttpExporter(),
                                        settings=trace_settings,
                                    )
                                )
                            trigger_poll_interval = (
                                0.0  # Polling disabled for production jobs
                            )

                        async def execute_debug_runtime():
                            chat_runtime: UiPathRuntimeProtocol | None = None
                            workspace: Workspace | None = None
                            hydration_runtime: HydrationRuntime | None = None
                            conversational_workspace_runtime: (
                                ConversationalWorkspaceRuntime | None
                            ) = None
                            debug_runtime: UiPathRuntimeProtocol | None = None
                            mock_runtime: UiPathRuntimeProtocol | None = None
                            runtime: UiPathRuntimeProtocol | None = None
                            try:
                                debug_bridge: UiPathDebugProtocol = get_debug_bridge(
                                    ctx, attach=attach_mode
                                )
                                new_runtime_kwargs: dict[str, Any] = {}
                                if governance_bootstrap is not None:
                                    new_runtime_kwargs["evaluator"] = (
                                        governance_bootstrap.evaluator
                                    )
                                runtime = await factory.new_runtime(
                                    entrypoint,
                                    governance_runtime_id,
                                    **new_runtime_kwargs,
                                )

                                if governance_bootstrap is not None:
                                    runtime = governance_bootstrap.wrap_runtime(
                                        runtime,
                                        agent_name=entrypoint,
                                        runtime_id=governance_runtime_id,
                                    )

                                delegate = runtime
                                if (
                                    ctx.job_id is not None
                                    and factory_settings is not None
                                    and factory_settings.managed_workspace
                                ):
                                    storage = await factory.get_storage()
                                    if storage is None:
                                        raise RuntimeError(
                                            "Runtime factory advertises managed workspace "
                                            "support but provides no storage"
                                        )

                                    client = UiPath()
                                    workspace = Workspace.create()
                                    workspace.path = workspace.path.resolve()
                                    hydrator = WorkspaceHydrator(
                                        workspace_path=workspace.path,
                                        attachments=client.attachments,
                                        jobs=client.jobs,
                                        current_job_key=ctx.job_id,
                                        folder_key=ctx.folder_key,
                                    )
                                    registry_store = WorkspaceRegistryStore(
                                        storage, ctx.job_id
                                    )
                                    hydration_runtime = HydrationRuntime(
                                        runtime,
                                        workspace=workspace,
                                        hydrator=hydrator,
                                        registry_store=registry_store,
                                    )
                                    delegate = hydration_runtime

                                    if (
                                        ctx.conversation_id is not None
                                        and ctx.exchange_id is not None
                                    ):
                                        conversational_workspace_runtime = (
                                            ConversationalWorkspaceRuntime(
                                                hydration_runtime,
                                                hydrator=hydrator,
                                            )
                                        )
                                        delegate = conversational_workspace_runtime

                                if ctx.conversation_id and ctx.exchange_id:
                                    chat_bridge: UiPathChatProtocol = get_chat_bridge(
                                        context=ctx
                                    )
                                    chat_runtime = UiPathChatRuntime(
                                        delegate=delegate, chat_bridge=chat_bridge
                                    )
                                    delegate = chat_runtime

                                debug_runtime = UiPathDebugRuntime(
                                    delegate=delegate,
                                    debug_bridge=debug_bridge,
                                    trigger_poll_interval=trigger_poll_interval,
                                )

                                schema = await runtime.get_schema()
                                agent_model = None
                                if schema.metadata and "settings" in schema.metadata:
                                    agent_model = schema.metadata["settings"].get(
                                        "model"
                                    )

                                mocking_context = load_simulation_config(
                                    agent_model=agent_model
                                )

                                mock_runtime = UiPathMockRuntime(
                                    delegate=debug_runtime,
                                    mocking_context=mocking_context,
                                )

                                ctx.result = await mock_runtime.execute(
                                    ctx.get_input(),
                                    options=UiPathExecuteOptions(resume=resume),
                                )
                            finally:
                                cleanup = AsyncExitStack()
                                if hydration_runtime is None:
                                    if runtime is not None:
                                        cleanup.push_async_callback(runtime.dispose)
                                    if workspace is not None:
                                        cleanup.push_async_callback(workspace.dispose)
                                if hydration_runtime is not None:
                                    cleanup.push_async_callback(
                                        hydration_runtime.dispose
                                    )
                                if conversational_workspace_runtime is not None:
                                    cleanup.push_async_callback(
                                        conversational_workspace_runtime.dispose
                                    )
                                if chat_runtime:
                                    cleanup.push_async_callback(chat_runtime.dispose)
                                if debug_runtime is not None:
                                    cleanup.push_async_callback(debug_runtime.dispose)
                                if mock_runtime is not None:
                                    cleanup.push_async_callback(mock_runtime.dispose)
                                await cleanup.aclose()

                        if project_id := UiPathConfig.project_id:
                            studio_client = StudioClient(project_id)

                            async with ResourceOverwritesContext(
                                lambda: studio_client.get_resource_overwrites()
                            ):
                                await execute_debug_runtime()
                        else:
                            logger.info(
                                "No UIPATH_PROJECT_ID configured, executing without resource overwrites"
                            )
                            await execute_debug_runtime()

                    finally:
                        try:
                            if governance_bootstrap is not None:
                                governance_bootstrap.dispose()
                            if factory:
                                await factory.dispose()
                        finally:
                            trace_manager.shutdown()

            asyncio.run(execute_debug_runtime())
        except Exception as e:
            console.error(
                f"Error occurred: {e or 'Execution failed'}", include_traceback=True
            )


if __name__ == "__main__":
    debug()
