from typing import AsyncIterator

from uipath.platform.connections import ConnectionsService
from uipath.platform.errors import EnrichedException, FolderNotFoundException
from uipath.platform.resource_catalog import (
    Resource,
    ResourceCatalogService,
    ResourceType,
)

from .._utils._studio_project import (
    ReferencedResourceFolder,
    ReferencedResourceRequest,
    VirtualResourceRequest,
)
from ..models.runtime_schema import BindingResource, Bindings
from ._resource_actions import CreateReference, CreateVirtual, ResourceAction, Skip

_NOT_FOUND_SUFFIX = "was not found and will not be added to the solution."


async def resolve_bindings(
    bindings: Bindings,
    resource_catalog: ResourceCatalogService,
    connections: ConnectionsService,
    supported_virtual_kinds: set[str],
) -> AsyncIterator[ResourceAction]:
    """Yield one ResourceAction per importable binding.

    Bindings that should be silently ignored (e.g. guardrail bindings without a
    folderPath) are filtered out here.
    """
    for binding in bindings.resources:
        action = await _resolve_binding(
            binding, resource_catalog, connections, supported_virtual_kinds
        )
        if action is not None:
            yield action


async def _resolve_binding(
    binding: BindingResource,
    resource_catalog: ResourceCatalogService,
    connections: ConnectionsService,
    supported_virtual_kinds: set[str],
) -> ResourceAction | None:
    if binding.resource == "connection":
        return await _resolve_connection(binding, resource_catalog, connections)
    return await _resolve_regular(binding, resource_catalog, supported_virtual_kinds)


async def _resolve_connection(
    binding: BindingResource,
    resource_catalog: ResourceCatalogService,
    connections: ConnectionsService,
) -> ResourceAction | None:
    connection_id_value = binding.value.get("ConnectionId")
    if connection_id_value is None:
        raise ValueError(
            f"Connection binding {binding.key!r} is missing required field 'ConnectionId'"
        )
    connection_key = connection_id_value.default_value

    try:
        connection = await connections.retrieve_async(connection_key)
    except EnrichedException:
        connector_name = (binding.metadata or {}).get("Connector")
        return Skip(
            message=(
                f"Connection with key '{connection_key}' of type "
                f"'{connector_name}' {_NOT_FOUND_SUFFIX}"
            )
        )

    resource_name: str = connection.name
    folder_path: str = connection.folder.get("path")

    found = await _find_in_resource_catalog(
        resource_catalog, "connection", resource_name, folder_path
    )
    if found is None:
        return Skip(
            message=(
                f"Resource '{resource_name}' of type 'connection' at folder path "
                f"'{folder_path}' {_NOT_FOUND_SUFFIX}"
            )
        )
    return _build_create_reference(found, resource_name)


async def _resolve_regular(
    binding: BindingResource,
    resource_catalog: ResourceCatalogService,
    supported_virtual_kinds: set[str],
) -> ResourceAction | None:
    name_value = binding.value.get("name")
    folder_path_value = binding.value.get("folderPath")
    if not folder_path_value:
        # guardrail resource, nothing to import
        return None
    if name_value is None:
        raise ValueError(f"Binding {binding.key!r} is missing required field 'name'")
    resource_name: str = name_value.default_value
    folder_path: str = folder_path_value.default_value
    resource_type: str = binding.resource

    found = await _find_in_resource_catalog(
        resource_catalog, resource_type, resource_name, folder_path
    )
    if found is not None:
        return _build_create_reference(found, resource_name)

    if resource_type not in supported_virtual_kinds:
        return Skip(
            message=(
                f"Cannot create virtual resource '{resource_name}' — "
                f"kind '{resource_type}' is not supported."
            )
        )

    sub_type: str | None = (binding.metadata or {}).get("SubType")
    return CreateVirtual(
        request=VirtualResourceRequest(
            kind=resource_type,
            name=resource_name,
            type=sub_type,
        )
    )


async def _find_in_resource_catalog(
    resource_catalog: ResourceCatalogService,
    resource_type: str,
    name: str,
    folder_path: str,
) -> Resource | None:
    """Look up a single resource in the Resource Catalog.

    Returns the first match or None if the catalog can't search this kind, the
    folder is unknown, or no resource matches.
    """
    catalog_type = next(
        (m for m in ResourceType if m.value == resource_type.lower()), None
    )
    if catalog_type is None:
        return None

    resources = resource_catalog.list_by_type_async(
        resource_type=catalog_type, name=name, folder_path=folder_path
    )
    try:
        return await anext(resources, None)
    except FolderNotFoundException:
        return None
    finally:
        await resources.aclose()


def _build_create_reference(
    found_resource: Resource, resource_name: str
) -> CreateReference:
    folder = next(iter(found_resource.folders))
    return CreateReference(
        request=ReferencedResourceRequest(
            key=found_resource.resource_key,
            kind=found_resource.resource_type,
            type=found_resource.resource_sub_type,
            folder=ReferencedResourceFolder(
                folder_key=folder.key,
                fully_qualified_name=folder.fully_qualified_name,
                path=folder.path,
            ),
        ),
        resource_name=resource_name,
        kind=found_resource.resource_type,
        sub_type=found_resource.resource_sub_type,
    )
