from contextlib import AsyncExitStack

from uipath.platform import UiPath
from uipath.runtime import (
    ConversationalWorkspaceRuntime,
    HydrationRuntime,
    UiPathRuntimeContext,
    UiPathRuntimeFactoryProtocol,
    UiPathRuntimeProtocol,
    Workspace,
    WorkspaceHydrator,
    WorkspaceRegistryStore,
)


async def wrap_with_managed_workspace(
    delegate: UiPathRuntimeProtocol,
    *,
    context: UiPathRuntimeContext,
    factory: UiPathRuntimeFactoryProtocol,
    enabled: bool,
    cleanup: AsyncExitStack,
) -> UiPathRuntimeProtocol:
    if context.job_id is None or not enabled:
        return delegate

    storage = await factory.get_storage()
    if storage is None:
        raise RuntimeError(
            "Runtime factory advertises managed workspace support but provides no storage"
        )

    client = UiPath()
    workspace = Workspace.create()
    try:
        workspace.path = workspace.path.resolve()
        hydrator = WorkspaceHydrator(
            workspace_path=workspace.path,
            attachments=client.attachments,
            jobs=client.jobs,
            current_job_key=context.job_id,
            folder_key=context.folder_key,
        )
        registry_store = WorkspaceRegistryStore(storage, context.job_id)
        hydration_runtime = HydrationRuntime(
            delegate,
            workspace=workspace,
            hydrator=hydrator,
            registry_store=registry_store,
        )

        if context.conversation_id is None or context.exchange_id is None:
            cleanup.push_async_callback(hydration_runtime.dispose)
            return hydration_runtime

        conversational_runtime = ConversationalWorkspaceRuntime(
            hydration_runtime,
            hydrator=hydrator,
            registry_store=registry_store,
        )
        cleanup.push_async_callback(hydration_runtime.dispose)
        cleanup.push_async_callback(conversational_runtime.dispose)
        return conversational_runtime
    except BaseException:
        await workspace.dispose()
        raise
