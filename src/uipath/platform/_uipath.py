from functools import cached_property
from typing import Optional

from pydantic import ValidationError

from .._utils._auth import resolve_config_from_env
from .action_center import TasksService
from .chat import ConversationsService, UiPathLlmChatService, UiPathOpenAIService
from .common import (
    ApiClient,
    ExternalApplicationService,
    UiPathApiConfig,
    UiPathExecutionContext,
)
from .connections import ConnectionsService
from .context_grounding import ContextGroundingService
from .documents import DocumentsService
from .entities import EntitiesService
from .errors import BaseUrlMissingError, SecretMissingError
from .guardrails import GuardrailsService
from .orchestrator import (
    AssetsService,
    AttachmentsService,
    BucketsService,
    FolderService,
    JobsService,
    McpService,
    ProcessesService,
    QueuesService,
)
from .resource_catalog import ResourceCatalogService


def _has_valid_client_credentials(
    client_id: Optional[str], client_secret: Optional[str]
) -> bool:
    if bool(client_id) != bool(client_secret):
        raise ValueError("Both client_id and client_secret must be provided together.")
    return bool(client_id and client_secret)


class UiPath:
    def __init__(
        self,
        *,
        base_url: Optional[str] = None,
        secret: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        scope: Optional[str] = None,
        debug: bool = False,
    ) -> None:
        try:
            if _has_valid_client_credentials(client_id, client_secret):
                assert client_id and client_secret
                service = ExternalApplicationService(base_url)
                token_data = service.get_token_data(client_id, client_secret, scope)
                base_url, secret = service._base_url, token_data.access_token
            else:
                base_url, secret = resolve_config_from_env(base_url, secret)

            self._config = UiPathApiConfig(
                base_url=base_url,
                secret=secret,
            )
        except ValidationError as e:
            for error in e.errors():
                if error["loc"][0] == "base_url":
                    raise BaseUrlMissingError() from e
                elif error["loc"][0] == "secret":
                    raise SecretMissingError() from e
        self._execution_context = UiPathExecutionContext()

    @property
    def api_client(self) -> ApiClient:
        return ApiClient(self._config, self._execution_context)

    @property
    def assets(self) -> AssetsService:
        return AssetsService(self._config, self._execution_context)

    @cached_property
    def attachments(self) -> AttachmentsService:
        return AttachmentsService(self._config, self._execution_context)

    @property
    def processes(self) -> ProcessesService:
        return ProcessesService(self._config, self._execution_context, self.attachments)

    @property
    def tasks(self) -> TasksService:
        return TasksService(self._config, self._execution_context)

    @cached_property
    def buckets(self) -> BucketsService:
        return BucketsService(self._config, self._execution_context)

    @cached_property
    def connections(self) -> ConnectionsService:
        return ConnectionsService(self._config, self._execution_context, self.folders)

    @property
    def context_grounding(self) -> ContextGroundingService:
        return ContextGroundingService(
            self._config,
            self._execution_context,
            self.folders,
            self.buckets,
        )

    @property
    def documents(self) -> DocumentsService:
        return DocumentsService(self._config, self._execution_context)

    @property
    def queues(self) -> QueuesService:
        return QueuesService(self._config, self._execution_context)

    @property
    def jobs(self) -> JobsService:
        return JobsService(self._config, self._execution_context)

    @cached_property
    def folders(self) -> FolderService:
        return FolderService(self._config, self._execution_context)

    @property
    def llm_openai(self) -> UiPathOpenAIService:
        return UiPathOpenAIService(self._config, self._execution_context)

    @property
    def llm(self) -> UiPathLlmChatService:
        return UiPathLlmChatService(self._config, self._execution_context)

    @property
    def entities(self) -> EntitiesService:
        return EntitiesService(self._config, self._execution_context)

    @cached_property
    def resource_catalog(self) -> ResourceCatalogService:
        return ResourceCatalogService(
            self._config, self._execution_context, self.folders
        )

    @property
    def conversational(self) -> ConversationsService:
        return ConversationsService(self._config, self._execution_context)

    @property
    def mcp(self) -> McpService:
        return McpService(self._config, self._execution_context, self.folders)

    @property
    def guardrails(self) -> GuardrailsService:
        return GuardrailsService(self._config, self._execution_context)
