import asyncio
from typing import AsyncIterator
from urllib.parse import urlparse

import click

from uipath.platform.common import UiPathConfig
from uipath.platform.errors import EnrichedException, FolderNotFoundException

from ..platform.resource_catalog import ResourceType
from ._push.sw_file_handler import SwFileHandler
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
    ReferencedResourceFolder,
    ReferencedResourceRequest,
    Status,
    StudioClient,
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


async def create_resources(studio_client: StudioClient):
    console.info("\nImporting referenced resources to Studio Web project...")

    from uipath.platform import UiPath

    uipath = UiPath()
    resource_catalog = uipath.resource_catalog
    connections = uipath.connections

    with open(UiPathConfig.bindings_file_path, "r") as f:
        bindings_file_content = f.read()

    bindings = Bindings.model_validate_json(bindings_file_content)

    resources_not_found = 0
    resources_unchanged = 0
    resources_created = 0
    resource_updated = 0

    for bindings_resource in bindings.resources:
        not_found_warning = "was not found and will not be added to the solution."
        found_resource = None
        resource_type = bindings_resource.resource
        if resource_type == "connection":
            connection_key_resource_value = bindings_resource.value.get("ConnectionId")
            assert connection_key_resource_value
            connection_key = connection_key_resource_value.default_value
            try:
                connection = await connections.retrieve_async(connection_key)
            except EnrichedException:
                resources_not_found += 1
                assert bindings_resource.metadata is not None
                connector_name = bindings_resource.metadata.get("Connector")
                console.warning(
                    f"Connection with key '{connection_key}' of type '{connector_name}' "
                    f"{not_found_warning}"
                )
                continue
            resource_name = connection.name
            folder_path = connection.folder.get("path")
        else:
            name_resource_value = bindings_resource.value.get("name")
            folder_path_resource_value = bindings_resource.value.get("folderPath")
            assert name_resource_value and folder_path_resource_value
            resource_name = name_resource_value.default_value
            folder_path = folder_path_resource_value.default_value

        resources = resource_catalog.list_by_type_async(
            resource_type=ResourceType.from_string(resource_type),
            name=resource_name,
            folder_path=folder_path,
        )

        try:
            async for resource in resources:
                found_resource = resource
                break
            await resources.aclose()

        except FolderNotFoundException:
            pass

        if not found_resource:
            console.warning(
                f"Resource '{resource_name}' of type '{resource_type}' at folder path '{folder_path}' "
                f"{not_found_warning}"
            )
            resources_not_found += 1
            continue

        referenced_resource_request = ReferencedResourceRequest(
            key=found_resource.resource_key,
            kind=found_resource.resource_type,
            type=found_resource.resource_sub_type,
            folder=next(
                ReferencedResourceFolder(
                    folder_key=folder.key,
                    fully_qualified_name=folder.fully_qualified_name,
                    path=folder.path,
                )
                for folder in found_resource.folders
            ),
        )
        response = await studio_client.create_referenced_resource(
            referenced_resource_request
        )

        resource_details = (
            f"(kind = {click.style(found_resource.resource_type, fg='cyan')}, "
            f"type = {click.style(found_resource.resource_sub_type, fg='cyan')})"
        )

        match response.status:
            case Status.ADDED:
                console.success(
                    f"Created reference for resource: {click.style(resource_name, fg='cyan')} "
                    f"{resource_details}"
                )
                resources_created += 1
            case Status.UNCHANGED:
                console.info(
                    f"Resource reference already exists ({click.style('unchanged', fg='yellow')}): {click.style(resource_name, fg='cyan')} "
                    f"{resource_details}"
                )
                resources_unchanged += 1
            case Status.UPDATED:
                console.info(
                    f"Resource reference already exists ({click.style('updated', fg='blue')}): {click.style(resource_name, fg='cyan')} "
                    f"{resource_details}"
                )
                resource_updated += 1

    total_resources = (
        resources_created + resources_unchanged + resources_not_found + resource_updated
    )
    console.info(
        f"\n \U0001f535 Resource import summary: {total_resources} total resources - "
        f"{click.style(str(resources_created), fg='green')} created, "
        f"{click.style(str(resource_updated), fg='blue')} updated, "
        f"{click.style(str(resources_unchanged), fg='yellow')} unchanged, "
        f"{click.style(str(resources_not_found), fg='red')} not found"
    )


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
    "root", type=click.Path(exists=True, file_okay=False, dir_okay=True), default="."
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
def push(root: str, ignore_resources: bool, nolock: bool, overwrite: bool) -> None:
    """Push local project files to Studio Web.

    This command pushes the local project files to a UiPath Studio Web project.
    It ensures that the remote project structure matches the local files by:
    - Updating existing files that have changed
    - Uploading new files
    - Deleting remote files that no longer exist locally
    - Optionally managing the UV lock file

    Args:
        root: The root directory of the project
        ignore_resources: Whether to skip importing the referenced resources
        nolock: Whether to skip UV lock operations and exclude uv.lock from push
        overwrite: Whether to automatically overwrite remote files without prompts

    Environment Variables:
        UIPATH_PROJECT_ID: Required. The ID of the UiPath Cloud project

    Example:
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
        return

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
