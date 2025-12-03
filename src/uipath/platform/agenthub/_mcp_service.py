from typing import Any, Dict

from ..._config import Config
from ..._execution_context import ExecutionContext
from ..._folder_context import FolderContext
from ..._utils import Endpoint, RequestSpec, header_folder
from ...tracing import traced
from ..common._base_service import BaseService
from ..common.paging import PagedResult
from ..orchestrator._folder_service import FolderService
from ..orchestrator.mcp import McpServer

# Pagination limits
MAX_PAGE_SIZE = 1000  # Maximum items per page (top parameter)
MAX_SKIP_OFFSET = 10000  # Maximum skip offset for offset-based pagination


class McpService(FolderContext, BaseService):
    """Service for managing MCP (Model Context Protocol) servers in UiPath.

    MCP servers provide contextual information and capabilities that can be used
    by AI agents and automation processes.
    """

    def __init__(
        self,
        config: Config,
        execution_context: ExecutionContext,
        folders_service: FolderService,
    ) -> None:
        super().__init__(config=config, execution_context=execution_context)
        self._folders_service = folders_service

    @traced(name="mcp_list", run_type="uipath")
    def list(
        self,
        *,
        folder_path: str | None = None,
        skip: int = 0,
        top: int = 100,
    ) -> PagedResult[McpServer]:
        """List MCP servers with offset-based pagination.

        Returns a single page of results with pagination metadata.

        Args:
            folder_path: The path of the folder to list servers from
            skip: Number of servers to skip (default 0, max 10000)
            top: Maximum number of servers to return (default 100, max 1000)

        Returns:
            PagedResult[McpServer]: Page containing servers and pagination metadata

        Raises:
            ValueError: If skip < 0, skip > 10000, top < 1, or top > 1000

        Examples:
            >>> # Get first page
            >>> result = sdk.mcp.list(top=100)
            >>> for server in result.items:
            ...     print(f"{server.name} - {server.slug}")
            >>>
            >>> # Check pagination metadata
            >>> if result.has_more:
            ...     print(f"More results available. Current: skip={result.skip}, top={result.top}")
            >>>
            >>> # Manual pagination to get all servers
            >>> skip = 0
            >>> top = 100
            >>> all_servers = []
            >>> while True:
            ...     result = sdk.mcp.list(skip=skip, top=top)
            ...     all_servers.extend(result.items)
            ...     if not result.has_more:
            ...         break
            ...     skip += top
            >>>
            >>> # Helper function for complete iteration
            >>> def iter_all_servers(sdk, top=100, **filters):
            ...     skip = 0
            ...     while True:
            ...         result = sdk.mcp.list(skip=skip, top=top, **filters)
            ...         yield from result.items
            ...         if not result.has_more:
            ...             break
            ...         skip += top
            >>>
            >>> # Usage
            >>> for server in iter_all_servers(sdk, folder_path="MyFolder"):
            ...     process_server(server)
        """
        if skip < 0:
            raise ValueError("skip must be >= 0")
        if skip > MAX_SKIP_OFFSET:
            raise ValueError(
                f"skip must be <= {MAX_SKIP_OFFSET} (requested: {skip}). "
                f"Use pagination with skip and top parameters to retrieve larger datasets."
            )
        if top < 1:
            raise ValueError("top must be >= 1")
        if top > MAX_PAGE_SIZE:
            raise ValueError(
                f"top must be <= {MAX_PAGE_SIZE} (requested: {top}). "
                f"Use pagination with skip and top parameters to retrieve larger datasets."
            )

        spec = self._list_spec(
            folder_path=folder_path,
            skip=skip,
            top=top,
        )

        response = self.request(
            spec.method,
            url=spec.endpoint,
            params=spec.params,
            headers=spec.headers,
        ).json()

        servers = [McpServer.model_validate(server) for server in response]

        return PagedResult(
            items=servers,
            has_more=len(servers) == top,
            skip=skip,
            top=top,
        )

    @traced(name="mcp_list", run_type="uipath")
    async def list_async(
        self,
        *,
        folder_path: str | None = None,
        skip: int = 0,
        top: int = 100,
    ) -> PagedResult[McpServer]:
        """Async version of list() with offset-based pagination.

        Returns a single page of results with pagination metadata.

        Args:
            folder_path: The path of the folder to list servers from
            skip: Number of servers to skip (default 0, max 10000)
            top: Maximum number of servers to return (default 100, max 1000)

        Returns:
            PagedResult[McpServer]: Page containing servers and pagination metadata

        Raises:
            ValueError: If skip < 0, skip > 10000, top < 1, or top > 1000

        Examples:
            >>> # Get first page
            >>> result = await sdk.mcp.list_async(top=100)
            >>> for server in result.items:
            ...     print(f"{server.name} - {server.slug}")
            >>>
            >>> # Manual pagination
            >>> skip = 0
            >>> top = 100
            >>> all_servers = []
            >>> while True:
            ...     result = await sdk.mcp.list_async(skip=skip, top=top)
            ...     all_servers.extend(result.items)
            ...     if not result.has_more:
            ...         break
            ...     skip += top
        """
        if skip < 0:
            raise ValueError("skip must be >= 0")
        if skip > MAX_SKIP_OFFSET:
            raise ValueError(
                f"skip must be <= {MAX_SKIP_OFFSET} (requested: {skip}). "
                f"Use pagination with skip and top parameters to retrieve larger datasets."
            )
        if top < 1:
            raise ValueError("top must be >= 1")
        if top > MAX_PAGE_SIZE:
            raise ValueError(
                f"top must be <= {MAX_PAGE_SIZE} (requested: {top}). "
                f"Use pagination with skip and top parameters to retrieve larger datasets."
            )

        spec = self._list_spec(
            folder_path=folder_path,
            skip=skip,
            top=top,
        )

        response = (
            await self.request_async(
                spec.method,
                url=spec.endpoint,
                params=spec.params,
                headers=spec.headers,
            )
        ).json()

        servers = [McpServer.model_validate(server) for server in response]

        return PagedResult(
            items=servers,
            has_more=len(servers) == top,
            skip=skip,
            top=top,
        )

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
        skip: int,
        top: int,
    ) -> RequestSpec:
        folder_key = self._folders_service.retrieve_folder_key(folder_path)

        params: Dict[str, Any] = {"$skip": skip, "$top": top}

        return RequestSpec(
            method="GET",
            endpoint=Endpoint("/agenthub_/api/servers"),
            params=params,
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
