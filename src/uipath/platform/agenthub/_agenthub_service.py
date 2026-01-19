from typing import Any

from ..._utils import Endpoint, RequestSpec, header_folder
from ..common import BaseService, FolderContext, UiPathApiConfig, UiPathExecutionContext
from ..orchestrator import FolderService
from .agenthub import LlmModel


class AgentHubService(FolderContext, BaseService):
    """Service class for interacting with AgentHub platform service."""

    def __init__(
        self,
        config: UiPathApiConfig,
        execution_context: UiPathExecutionContext,
        folder_service: FolderService,
    ) -> None:
        self._folder_service = folder_service
        super().__init__(config=config, execution_context=execution_context)

    def get_available_llm_models(
        self, headers: dict[str, Any] | None = None
    ) -> list[LlmModel]:
        """Fetch available models from LLM Gateway discovery endpoint.

        Returns:
           List of available models and their configurations.
        """
        spec = self._available_models_spec(headers=headers)

        response = self.request(
            spec.method,
            spec.endpoint,
            params=spec.params,
            headers=spec.headers,
        )
        return [
            LlmModel.model_validate(available_model)
            for available_model in response.json()
        ]

    async def get_available_llm_models_async(
        self, headers: dict[str, Any] | None = None
    ) -> list[LlmModel]:
        """Asynchronously fetch available models from LLM Gateway discovery endpoint.

        Returns:
           List of available models and their configurations.
        """
        spec = self._available_models_spec(headers=headers)

        response = await self.request_async(
            spec.method,
            spec.endpoint,
            params=spec.params,
            headers=spec.headers,
        )
        return [
            LlmModel.model_validate(available_model)
            for available_model in response.json()
        ]

    def invoke_system_agent(
        self,
        *,
        agent_name: str,
        entrypoint: str,
        input_arguments: dict[str, Any] | None = None,
        folder_key: str | None = None,
        folder_path: str | None = None,
        headers: dict[str, Any] | None = None,
    ) -> str:
        """Start a system agent job.

        Args:
            agent_name: The name of the system agent to invoke.
            entrypoint: The entry point to execute.
            input_arguments: Optional input arguments to pass to the agent.
            folder_key: Optional folder key to override the default folder context.
            folder_path: Optional folder path to override the default folder context.

        Returns:
            str: The started job's key.
        """
        folder_key = self._resolve_folder_key(folder_key, folder_path)

        spec = self._start_spec(
            agent_name=agent_name,
            entrypoint=entrypoint,
            input_arguments=input_arguments,
            folder_key=folder_key,
            headers=headers,
        )

        response = self.request(
            spec.method,
            url=spec.endpoint,
            json=spec.json,
            headers=spec.headers,
        )

        response_data = response.json()

        return response_data["key"]

    async def invoke_system_agent_async(
        self,
        *,
        agent_name: str,
        entrypoint: str,
        input_arguments: dict[str, Any] | None = None,
        folder_key: str | None = None,
        folder_path: str | None = None,
        headers: dict[str, Any] | None = None,
    ) -> str:
        """Asynchronously start a system agent and return the job.

        Args:
            agent_name: The name of the system agent to invoke.
            entrypoint: The entry point to execute.
            input_arguments: Optional input arguments to pass to the agent.
            folder_key: Optional folder key to override the default folder context.
            folder_path: Optional folder path to override the default folder context.

        Returns:
            str: The started job's key.

        """
        folder_key = self._resolve_folder_key(folder_key, folder_path)

        spec = self._start_spec(
            agent_name=agent_name,
            entrypoint=entrypoint,
            input_arguments=input_arguments,
            folder_key=folder_key,
            headers=headers,
        )

        response = await self.request_async(
            spec.method,
            url=spec.endpoint,
            json=spec.json,
            headers=spec.headers,
        )

        response_data = response.json()

        return response_data["key"]

    def _start_spec(
        self,
        agent_name: str,
        entrypoint: str,
        input_arguments: dict[str, Any] | None,
        folder_key: str,
        headers: dict[str, Any] | None,
    ) -> RequestSpec:
        """Build the request specification for starting a system agent.

        Args:
            agent_name: The name of the system agent.
            entrypoint: The entry point to execute.
            input_arguments: Input arguments for the agent.
            folder_key: Folder key for scoping.

        Returns:
            RequestSpec: The request specification with endpoint, method, headers, and body.
        """
        return RequestSpec(
            method="POST",
            endpoint=Endpoint(f"agenthub_/api/systemagents/{agent_name}/start"),
            headers=header_folder(folder_key, None) | (headers or {}),
            json={
                "EntryPoint": entrypoint,
                "InputArguments": input_arguments or {},
            },
        )

    def _resolve_folder_key(
        self, folder_key: str | None, folder_path: str | None
    ) -> str:
        if folder_key is None and folder_path is not None:
            folder_key = self._folder_service.retrieve_key(folder_path=folder_path)

        if folder_key is None and folder_path is None:
            folder_key = self._folder_key or (
                self._folder_service.retrieve_key(folder_path=self._folder_path)
                if self._folder_path
                else None
            )

        if folder_key is None:
            raise ValueError("AgentHubClient: Failed to resolve folder key")

        return folder_key

    def _available_models_spec(self, headers: dict[str, Any] | None) -> RequestSpec:
        return RequestSpec(
            method="GET",
            endpoint=Endpoint("/agenthub_/llm/api/discovery"),
            headers=headers or {},
        )
