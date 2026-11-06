"""Host-managed workspace persistence for runtimes that opt in.

A factory opts in through ``UiPathRuntimeFactorySettings.managed_workspace``.
The host then gives each job run a workspace folder, exposed to agent code
through ``uipath.runtime.get_workspace_path()``, and persists the folder as
job attachments across suspend and resume.
"""

from __future__ import annotations

from uipath.platform import UiPath
from uipath.platform.common import UiPathConfig
from uipath.runtime import (
    HydrationPolicy,
    ManagedWorkspace,
    UiPathRuntimeFactoryProtocol,
    UiPathRuntimeFactorySettings,
    UiPathRuntimeProtocol,
    WorkspaceRegistryStore,
)

__all__ = ["wrap_with_managed_workspace"]


async def wrap_with_managed_workspace(
    runtime: UiPathRuntimeProtocol,
    *,
    factory: UiPathRuntimeFactoryProtocol,
    settings: UiPathRuntimeFactorySettings | None,
    runtime_id: str,
    job_id: str | None,
    conversation_id: str | None = None,
) -> UiPathRuntimeProtocol:
    """Wrap a runtime so its workspace survives suspend and resume.

    The runtime is returned unchanged unless the factory opts in, the run is a
    job, and the factory has storage for the workspace registry. Files are
    uploaded when the run suspends, and also when a conversational exchange
    ends successfully, because the next exchange resumes the same job.

    Args:
        runtime: Runtime returned by the factory.
        factory: Factory that created the runtime; provides registry storage.
        settings: The factory's settings.
        runtime_id: Runtime id the runtime was created with.
        job_id: Orchestrator job key, or ``None`` outside a job.
        conversation_id: Conversation id for conversational runs.

    Returns:
        The wrapped runtime, or ``runtime`` when no workspace applies.
    """
    if settings is None or not settings.managed_workspace or not job_id:
        return runtime

    storage = await factory.get_storage()
    if storage is None:
        return runtime

    managed = ManagedWorkspace(
        services=UiPath,
        runtime_id=runtime_id,
        job_key=job_id,
        folder_key=UiPathConfig.folder_key,
        registry_store=WorkspaceRegistryStore(storage, runtime_id),
    )
    return managed.wrap(
        runtime,
        policy=(
            HydrationPolicy.SUSPEND_OR_SUCCESS
            if conversation_id
            else HydrationPolicy.SUSPEND_ONLY
        ),
    )
