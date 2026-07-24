from typing import List
from urllib.parse import quote

from uipath.core.tracing import traced

from ..common._base_service import BaseService
from ..common._bindings import resource_override
from ..common._config import UiPathApiConfig
from ..common._execution_context import UiPathExecutionContext
from ..common._folder_context import FolderContext, header_folder
from ..common._models import Endpoint, RequestSpec
from ._folder_service import FolderService
from .mcp import McpServer


class McpService(FolderContext, BaseService):
    """Service for managing MCP (Model Context Protocol) servers in UiPath.

    MCP servers provide contextual information and capabilities that can be used
    by AI agents and automation processes.
    """

    def __init__(
        self,
        config: UiPathApiConfig,
        execution_context: UiPathExecutionContext,
        folders_service: FolderService,
    ) -> None:
        super().__init__(config=config, execution_context=execution_context)
        self._folders_service = folders_service

    @traced(name="mcp_list", run_type="uipath")
    def list(
        self,
        *,
        folder_path: str | None = None,
    ) -> List[McpServer]:
        """List all MCP servers.

        Args:
            folder_path (Optional[str]): The path of the folder to list servers from.

        Returns:
            List[McpServer]: A list of MCP servers with their configuration.

        Examples:
            ```python
            from uipath import UiPath

            client = UiPath()

            servers = client.mcp.list(folder_path="MyFolder")
            for server in servers:
                print(f"{server.name} - {server.slug}")
            ```
        """
        spec = self._list_spec(
            folder_path=folder_path,
        )

        response = self.request(
            spec.method,
            url=spec.endpoint,
            params=spec.params,
            headers=spec.headers,
        )

        return [McpServer.model_validate(server) for server in response.json()]

    @traced(name="mcp_list", run_type="uipath")
    async def list_async(
        self,
        *,
        folder_path: str | None = None,
    ) -> List[McpServer]:
        """Asynchronously list all MCP servers.

        Args:
            folder_path (Optional[str]): The path of the folder to list servers from.

        Returns:
            List[McpServer]: A list of MCP servers with their configuration.

        Examples:
            ```python
            import asyncio

            from uipath import UiPath

            sdk = UiPath()

            async def main():
                servers = await sdk.mcp.list_async(folder_path="MyFolder")
                for server in servers:
                    print(f"{server.name} - {server.slug}")

            asyncio.run(main())
            ```
        """
        spec = self._list_spec(
            folder_path=folder_path,
        )

        response = await self.request_async(
            spec.method,
            url=spec.endpoint,
            params=spec.params,
            headers=spec.headers,
        )

        return [McpServer.model_validate(server) for server in response.json()]

    @resource_override(resource_type="mcpServer", resource_identifier="name")
    @resource_override(resource_type="mcpServer", resource_identifier="slug")
    @traced(name="mcp_retrieve", run_type="uipath")
    def retrieve(
        self,
        name: str | None = None,
        *,
        slug: str | None = None,
        folder_path: str | None = None,
    ) -> McpServer:
        """Retrieve a specific MCP server by its display name or legacy slug.

        Args:
            name (Optional[str]): The display name of the server.
            slug (Optional[str]): The legacy slug identifier of the server.
            folder_path (Optional[str]): The path of the folder where the server is located.

        Returns:
            McpServer: The MCP server configuration.

        Examples:
            ```python
            from uipath import UiPath

            client = UiPath()

            server = client.mcp.retrieve(name="My Server", folder_path="MyFolder")
            print(f"Server: {server.name}, URL: {server.mcp_url}")
            ```
        """
        identifier = self._resolve_retrieve_identifier(name=name, slug=slug)
        spec = self._retrieve_spec(
            name=identifier,
            folder_path=folder_path,
        )

        response = self.request(
            spec.method,
            url=spec.endpoint,
            params=spec.params,
            headers=spec.headers,
        )

        return McpServer.model_validate(response.json())

    @resource_override(resource_type="mcpServer", resource_identifier="name")
    @resource_override(resource_type="mcpServer", resource_identifier="slug")
    @traced(name="mcp_retrieve", run_type="uipath")
    async def retrieve_async(
        self,
        name: str | None = None,
        *,
        slug: str | None = None,
        folder_path: str | None = None,
    ) -> McpServer:
        """Asynchronously retrieve an MCP server by its display name or legacy slug.

        Args:
            name (Optional[str]): The display name of the server.
            slug (Optional[str]): The legacy slug identifier of the server.
            folder_path (Optional[str]): The path of the folder where the server is located.

        Returns:
            McpServer: The MCP server configuration.

        Examples:
            ```python
            import asyncio

            from uipath import UiPath

            sdk = UiPath()

            async def main():
                server = await sdk.mcp.retrieve_async(name="My Server", folder_path="MyFolder")
                print(f"Server: {server.name}, URL: {server.mcp_url}")

            asyncio.run(main())
            ```
        """
        identifier = self._resolve_retrieve_identifier(name=name, slug=slug)
        spec = self._retrieve_spec(
            name=identifier,
            folder_path=folder_path,
        )

        response = await self.request_async(
            spec.method,
            url=spec.endpoint,
            params=spec.params,
            headers=spec.headers,
        )

        return McpServer.model_validate(response.json())

    @property
    def custom_headers(self) -> dict[str, str]:
        return self.folder_headers

    def _resolve_folder_key(self, folder_path: str | None) -> str | None:
        """Resolve folder key from folder_path, falling back to FolderContext."""
        if folder_path is not None:
            return self._folders_service.retrieve_folder_key(folder_path)

        return self._folder_key

    @staticmethod
    def _resolve_retrieve_identifier(
        name: str | None,
        slug: str | None,
    ) -> str:
        if name is not None and slug is not None:
            raise ValueError("Specify either 'name' or 'slug', not both.")
        if name is not None:
            return name
        if slug is not None:
            return slug
        raise TypeError("Either 'name' or 'slug' must be provided.")

    def _list_spec(
        self,
        *,
        folder_path: str | None,
    ) -> RequestSpec:
        folder_key = self._resolve_folder_key(folder_path)
        return RequestSpec(
            method="GET",
            endpoint=Endpoint("/agenthub_/api/servers"),
            headers={
                **header_folder(folder_key, None),
            },
        )

    def _retrieve_spec(
        self,
        name: str,
        *,
        folder_path: str | None,
    ) -> RequestSpec:
        folder_key = self._resolve_folder_key(folder_path)
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(f"/agenthub_/api/servers/{quote(name, safe='')}"),
            headers={
                **header_folder(folder_key, None),
            },
        )
