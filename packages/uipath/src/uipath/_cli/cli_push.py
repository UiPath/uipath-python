import asyncio
from typing import AsyncIterator
from urllib.parse import urlparse

import click

from uipath.platform.common import UiPathConfig
from uipath.platform.errors import EnrichedException

from ._push._resolvers import resolve_bindings
from ._push._resource_actions import (
    CreateReference,
    CreateVirtual,
    ResourceAction,
    Skip,
)
from ._push._summary import ResourceImportSummary
from ._push._virtual_kinds import fetch_supported_virtual_kinds
from ._push.sw_file_handler import SwFileHandler
from ._telemetry import track_command
from ._utils._common import ensure_coded_agent_project, may_override_files
from ._utils._console import ConsoleLogger
from ._utils._project_files import (
    Severity,
    UpdateEvent,
    ensure_config_file,
    get_project_config,
    validate_config,
    validate_project_files,
)
from ._utils._studio_project import (
    ProjectLockUnavailableError,
    Status,
    StudioClient,
    VirtualResourceRequest,
)
from ._utils._uv_helpers import handle_uv_operations
from .models.runtime_schema import Bindings
from .models.uipath_json_schema import PackOptions

console = ConsoleLogger()


def get_org_scoped_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    org_name, *_ = parsed.path.strip("/").split("/")

    org_scoped_url = f"{parsed.scheme}://{parsed.netloc}/{org_name}"
    return org_scoped_url


async def create_resources(studio_client: StudioClient) -> None:
    console.info("\nImporting referenced resources to Studio Web project...")

    from uipath.platform import UiPath

    uipath = UiPath()

    with open(UiPathConfig.bindings_file_path, "r") as f:
        bindings = Bindings.model_validate_json(f.read())

    supported_virtual_kinds = await fetch_supported_virtual_kinds(studio_client)

    summary = ResourceImportSummary()
    async for action in resolve_bindings(
        bindings,
        uipath.resource_catalog,
        uipath.connections,
        supported_virtual_kinds,
    ):
        await _execute_action(action, studio_client, summary)

    console.info(str(summary))


async def _execute_action(
    action: ResourceAction,
    studio_client: StudioClient,
    summary: ResourceImportSummary,
) -> None:
    match action:
        case Skip(message=message):
            console.warning(message)
            summary.not_found += 1

        case CreateVirtual(request=request):
            try:
                result = await studio_client.create_virtual_resource(request)
            except EnrichedException as e:
                console.warning(
                    f"Failed to create virtual resource '{request.name}' of type "
                    f"'{request.kind}': {e}"
                )
                summary.not_found += 1
                return
            label = _format_virtual_label(request)
            match result.status:
                case Status.ADDED:
                    console.success(f"{label} created successfully.")
                    summary.virtual_created += 1
                case Status.UNCHANGED:
                    console.info(f"{label} already exists. Skipping...")
                    summary.virtual_existing += 1

        case CreateReference(
            request=request,
            resource_name=resource_name,
            kind=kind,
            sub_type=sub_type,
        ):
            response = await studio_client.create_referenced_resource(request)
            details = (
                f"(kind = {click.style(kind, fg='cyan')}, "
                f"type = {click.style(sub_type, fg='cyan')})"
            )
            match response.status:
                case Status.ADDED:
                    console.success(
                        f"Created reference for resource: "
                        f"{click.style(resource_name, fg='cyan')} {details}"
                    )
                    summary.created += 1
                case Status.UNCHANGED:
                    console.info(
                        f"Resource reference already exists "
                        f"({click.style('unchanged', fg='yellow')}): "
                        f"{click.style(resource_name, fg='cyan')} {details}"
                    )
                    summary.unchanged += 1
                case Status.UPDATED:
                    console.info(
                        f"Resource reference already exists "
                        f"({click.style('updated', fg='blue')}): "
                        f"{click.style(resource_name, fg='cyan')} {details}"
                    )
                    summary.updated += 1


def _format_virtual_label(request: VirtualResourceRequest) -> str:
    parts = [
        f"Resource {click.style(request.name, fg='cyan')}",
        f" (kind: {click.style(request.kind, fg='yellow')}",
    ]
    if request.type:
        parts.append(f", type: {click.style(request.type, fg='yellow')}")
    if request.activity_name:
        parts.append(f", activity: {click.style(request.activity_name, fg='yellow')}")
    parts.append(")")
    return "".join(parts)


async def upload_source_files_to_project(
    project_id: str,
    pack_options: PackOptions | None,
    directory: str,
    studio_client: StudioClient | None = None,
    include_uv_lock: bool = True,
) -> AsyncIterator[UpdateEvent]:
    """Upload source files to UiPath project, yielding progress updates.

    This function handles the pushing of local files to the remote project:
    - Updates existing files that have changed
    - Uploads new files that don't exist remotely
    - Deletes remote files that no longer exist locally
    - Optionally includes the UV lock file

    Args:
        project_id: The ID of the UiPath project
        settings: Optional settings dictionary for file handling
        directory: The local directory to push
        include_uv_lock: Whether to include the uv.lock file

    Yields:
        FileOperationUpdate: Progress updates for each file operation

    Raises:
        ProjectPushError: If the push operation fails
    """
    sw_file_handler = SwFileHandler(
        project_id=project_id,
        directory=directory,
        studio_client=studio_client,
        include_uv_lock=include_uv_lock,
    )

    async for update in sw_file_handler.upload_source_files(pack_options):
        yield update


@click.command()
@click.argument(
    "root",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    default=".",
    metavar="",
)
@click.option(
    "--ignore-resources",
    is_flag=True,
    help="Skip importing the referenced resources to Studio Web solution",
)
@click.option(
    "--nolock",
    is_flag=True,
    help="Skip running uv lock and exclude uv.lock from the package",
)
@click.option(
    "--overwrite",
    is_flag=True,
    help="Automatically overwrite remote files without prompts",
)
@track_command("push")
def push(root: str, ignore_resources: bool, nolock: bool, overwrite: bool) -> None:
    """Push local project files to Studio Web.

    This command pushes the local project files to a UiPath Studio Web project.
    It ensures that the remote project structure matches the local files by:

    - Updating existing files that have changed
    - Uploading new files
    - Deleting remote files that no longer exist locally
    - Optionally managing the UV lock file

    **Environment Variables:**

    - `UIPATH_PROJECT_ID`: Required. The ID of the UiPath Cloud project

    **Example:**

        $ uipath push
        $ uipath push --nolock
        $ uipath push --overwrite
        $ uipath push --ignore-resources
    """
    ensure_config_file(root)
    config = get_project_config(root)
    validate_config(config)
    validate_project_files(root)

    project_id = UiPathConfig.project_id
    if not project_id:
        console.error("UIPATH_PROJECT_ID environment variable not found.")

    studio_client = StudioClient(project_id=project_id)

    asyncio.run(ensure_coded_agent_project(studio_client))

    if not overwrite:
        may_override = asyncio.run(may_override_files(studio_client, "remote"))
        if not may_override:
            console.info("Operation aborted.")
            return

    async def push_with_updates():
        """Wrapper to handle async iteration and display updates."""
        async for update in upload_source_files_to_project(
            project_id,
            config.get("packOptions", {}),
            root,
            studio_client,
            include_uv_lock=not nolock,
        ):
            match update.severity:
                case Severity.WARNING:
                    console.warning(update.message)
                case _:
                    console.info(update.message)

        if not ignore_resources:
            await create_resources(studio_client)

    console.log("Pushing UiPath project to Studio Web...")
    try:
        if not nolock:
            handle_uv_operations(root)

        asyncio.run(push_with_updates())

    except ProjectLockUnavailableError:
        console.error(
            "The project is temporarily locked. This could be due to modifications or active processes. Please wait a moment and try again."
        )
    except Exception as e:
        console.error(
            f"Failed to push UiPath project: {e}",
            include_traceback=not isinstance(e, EnrichedException),
        )
