"""Service for managing Remote A2A agents in UiPath AgentHub.

.. warning::
    This module is experimental and subject to change.
    The Remote A2A feature is in preview and its API may change in future releases.
"""

import warnings
from typing import Any, List

from ..common._base_service import BaseService
from ..common._config import UiPathApiConfig
from ..common._execution_context import UiPathExecutionContext
from ..common._folder_context import FolderContext, header_folder
from ..common._models import Endpoint, RequestSpec
from ..orchestrator import FolderService
from .remote_a2a import RemoteA2aAgent


class RemoteA2aService(FolderContext, BaseService):
    """Service for managing Remote A2A agents in UiPath AgentHub.

    .. warning::
        This service is experimental and subject to change.
    """

    def __init__(
        self,
        config: UiPathApiConfig,
        execution_context: UiPathExecutionContext,
        folders_service: FolderService,
    ) -> None:
        super().__init__(config=config, execution_context=execution_context)
        self._folders_service = folders_service

    def list(
        self,
        *,
        top: int | None = None,
        skip: int | None = None,
        search: str | None = None,
        folder_path: str | None = None,
    ) -> List[RemoteA2aAgent]:
        """List Remote A2A agents.

        .. warning::
            This method is experimental and subject to change.

        When called without folder_path, returns all agents across
        the tenant that the user has access to. When called with a folder,
        returns only agents in that folder.

        Args:
            top: Maximum number of agents to return.
            skip: Number of agents to skip (for pagination).
            search: Filter agents by name or slug.
            folder_path: Optional folder path to scope the query.

        Returns:
            List[RemoteA2aAgent]: A list of Remote A2A agents.

        Examples:
            ```python
            from uipath import UiPath

            client = UiPath()

            # List all agents across tenant
            agents = client.remote_a2a.list()
            for agent in agents:
                print(f"{agent.name} - {agent.slug}")

            # List with folder scope
            agents = client.remote_a2a.list(folder_path="MyFolder")
            ```
        """
        warnings.warn(
            "remote_a2a.list is experimental and subject to change.",
            stacklevel=2,
        )
        spec = self._list_spec(
            top=top,
            skip=skip,
            search=search,
            folder_path=folder_path,
        )
        response = self.request(
            spec.method,
            url=spec.endpoint,
            params=spec.params,
            headers=spec.headers,
        )
        data = response.json()
        return [RemoteA2aAgent.model_validate(agent) for agent in data.get("value", [])]

    async def list_async(
        self,
        *,
        top: int | None = None,
        skip: int | None = None,
        search: str | None = None,
        folder_path: str | None = None,
    ) -> List[RemoteA2aAgent]:
        """Asynchronously list Remote A2A agents.

        .. warning::
            This method is experimental and subject to change.

        Args:
            top: Maximum number of agents to return.
            skip: Number of agents to skip (for pagination).
            search: Filter agents by name or slug.
            folder_path: Optional folder path to scope the query.

        Returns:
            List[RemoteA2aAgent]: A list of Remote A2A agents.

        Examples:
            ```python
            import asyncio
            from uipath import UiPath

            sdk = UiPath()

            async def main():
                agents = await sdk.remote_a2a.list_async()
                for agent in agents:
                    print(f"{agent.name} - {agent.slug}")

            asyncio.run(main())
            ```
        """
        warnings.warn(
            "remote_a2a.list_async is experimental and subject to change.",
            stacklevel=2,
        )
        spec = self._list_spec(
            top=top,
            skip=skip,
            search=search,
            folder_path=folder_path,
        )
        response = await self.request_async(
            spec.method,
            url=spec.endpoint,
            params=spec.params,
            headers=spec.headers,
        )
        data = response.json()
        return [RemoteA2aAgent.model_validate(agent) for agent in data.get("value", [])]

    def retrieve(
        self,
        slug: str,
        *,
        folder_path: str | None = None,
    ) -> RemoteA2aAgent:
        """Retrieve a specific Remote A2A agent by slug.

        .. warning::
            This method is experimental and subject to change.

        Args:
            slug: The unique slug identifier for the agent.
            folder_path: The folder path where the agent is located.

        Returns:
            RemoteA2aAgent: The Remote A2A agent.

        Examples:
            ```python
            from uipath import UiPath

            client = UiPath()

            agent = client.remote_a2a.retrieve("weather", folder_path="MyFolder")
            print(f"Agent: {agent.name}, URL: {agent.a2a_url}")
            ```
        """
        warnings.warn(
            "remote_a2a.retrieve is experimental and subject to change.",
            stacklevel=2,
        )
        spec = self._retrieve_spec(slug=slug, folder_path=folder_path)
        response = self.request(
            spec.method,
            url=spec.endpoint,
            params=spec.params,
            headers=spec.headers,
        )
        return RemoteA2aAgent.model_validate(response.json())

    async def retrieve_async(
        self,
        slug: str,
        *,
        folder_path: str | None = None,
    ) -> RemoteA2aAgent:
        """Asynchronously retrieve a specific Remote A2A agent by slug.

        .. warning::
            This method is experimental and subject to change.

        Args:
            slug: The unique slug identifier for the agent.
            folder_path: The folder path where the agent is located.

        Returns:
            RemoteA2aAgent: The Remote A2A agent.

        Examples:
            ```python
            import asyncio
            from uipath import UiPath

            sdk = UiPath()

            async def main():
                agent = await sdk.remote_a2a.retrieve_async("weather", folder_path="MyFolder")
                print(f"Agent: {agent.name}, URL: {agent.a2a_url}")

            asyncio.run(main())
            ```
        """
        warnings.warn(
            "remote_a2a.retrieve_async is experimental and subject to change.",
            stacklevel=2,
        )
        spec = self._retrieve_spec(slug=slug, folder_path=folder_path)
        response = await self.request_async(
            spec.method,
            url=spec.endpoint,
            params=spec.params,
            headers=spec.headers,
        )
        return RemoteA2aAgent.model_validate(response.json())

    @property
    def custom_headers(self) -> dict[str, str]:
        return self.folder_headers

    def _list_spec(
        self,
        *,
        top: int | None,
        skip: int | None,
        search: str | None,
        folder_path: str | None,
    ) -> RequestSpec:
        headers = {}
        if folder_path is not None:
            folder_key = self._folders_service.retrieve_folder_key(folder_path)
            headers = header_folder(folder_key, None)

        params: dict[str, Any] = {}
        if top is not None:
            params["top"] = top
        if skip is not None:
            params["skip"] = skip
        if search is not None:
            params["search"] = search

        return RequestSpec(
            method="GET",
            endpoint=Endpoint("/agenthub_/api/remote-a2a-agents"),
            params=params,
            headers=headers,
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
            endpoint=Endpoint(f"/agenthub_/api/remote-a2a-agents/{slug}"),
            headers={
                **header_folder(folder_key, None),
            },
        )
