from typing import List

from ..._utils import Endpoint, RequestSpec, header_folder
from ...tracing import traced
from ..common import BaseService, FolderContext, UiPathApiConfig, UiPathExecutionContext
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

    @traced(name="mcp_retrieve", run_type="uipath")
    def retrieve(
        self,
        slug: str,
        *,
        folder_path: str | None = None,
    ) -> McpServer:
        """Retrieve a specific MCP server by its slug.

        Args:
            slug (str): The unique slug identifier for the server.
            folder_path (Optional[str]): The path of the folder where the server is located.

        Returns:
            McpServer: The MCP server configuration.

        Examples:
            ```python
            from uipath import UiPath

            client = UiPath()

            server = client.mcp.retrieve(slug="my-server-slug", folder_path="MyFolder")
            print(f"Server: {server.name}, URL: {server.mcp_url}")
            ```
        """
        spec = self._retrieve_spec(
            slug=slug,
            folder_path=folder_path,
        )

        response = self.request(
            spec.method,
            url=spec.endpoint,
            params=spec.params,
            headers=spec.headers,
        )

        return McpServer.model_validate(response.json())

    @traced(name="mcp_retrieve", run_type="uipath")
    async def retrieve_async(
        self,
        slug: str,
        *,
        folder_path: str | None = None,
    ) -> McpServer:
        """Asynchronously retrieve a specific MCP server by its slug.

        Args:
            slug (str): The unique slug identifier for the server.
            folder_path (Optional[str]): The path of the folder where the server is located.

        Returns:
            McpServer: The MCP server configuration.

        Examples:
            ```python
            import asyncio

            from uipath import UiPath

            sdk = UiPath()

            async def main():
                server = await sdk.mcp.retrieve_async(slug="my-server-slug", folder_path="MyFolder")
                print(f"Server: {server.name}, URL: {server.mcp_url}")

            asyncio.run(main())
            ```
        """
        spec = self._retrieve_spec(
            slug=slug,
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

    def _list_spec(
        self,
        *,
        folder_path: str | None,
    ) -> RequestSpec:
        folder_key = self._folders_service.retrieve_folder_key(folder_path)
        return RequestSpec(
            method="GET",
            endpoint=Endpoint("/agenthub_/api/servers"),
            headers={
                **header_folder(folder_key, None),
            },
        )

    def _retrieve_spec(
        self,
        slug: str,
        *,
        folder_path: str | None,
    ) -> RequestSpec:
        folder_key = self._folders_service.retrieve_folder_key(folder_path)
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(f"/agenthub_/api/servers/{slug}"),
            headers={
                **header_folder(folder_key, None),
            },
        )
