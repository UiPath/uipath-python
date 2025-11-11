from functools import cached_property
from typing import Optional

from pydantic import ValidationError

from ._config import Config
from ._execution_context import ExecutionContext
from ._services import (
    ActionsService,
    ApiClient,
    AssetsService,
    AttachmentsService,
    BucketsService,
    ConnectionsService,
    ContextGroundingService,
    DocumentsService,
    EntitiesService,
    FolderService,
    JobsService,
    ProcessesService,
    QueuesService,
    UiPathLlmChatService,
    UiPathOpenAIService,
)
from ._services.resource_catalog_service import ResourceCatalogService
from ._utils._auth import resolve_config
from ._utils._logs import setup_logging
from .models.errors import BaseUrlMissingError, SecretMissingError


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
            base_url, secret = resolve_config(
                base_url, secret, client_id, client_secret, scope
            )
            self._config = Config(
                base_url=base_url,
                secret=secret,
            )
        except ValidationError as e:
            for error in e.errors():
                if error["loc"][0] == "base_url":
                    raise BaseUrlMissingError() from e
                elif error["loc"][0] == "secret":
                    raise SecretMissingError() from e
        setup_logging(should_debug=debug)
        self._execution_context = ExecutionContext()

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
    def actions(self) -> ActionsService:
        return ActionsService(self._config, self._execution_context)

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
