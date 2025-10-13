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
from ._utils import setup_logging
from ._utils._auth import resolve_config
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
        self._folders_service: Optional[FolderService] = None
        self._buckets_service: Optional[BucketsService] = None
        self._attachments_service: Optional[AttachmentsService] = None
        self._connections_service: Optional[ConnectionsService] = None

        setup_logging(debug)
        self._execution_context = ExecutionContext()

    @property
    def api_client(self) -> ApiClient:
        return ApiClient(self._config, self._execution_context)

    @property
    def assets(self) -> AssetsService:
        return AssetsService(self._config, self._execution_context)

    @property
    def attachments(self) -> AttachmentsService:
        if not self._attachments_service:
            self._attachments_service = AttachmentsService(
                self._config, self._execution_context
            )
        return self._attachments_service

    @property
    def processes(self) -> ProcessesService:
        return ProcessesService(self._config, self._execution_context, self.attachments)

    @property
    def actions(self) -> ActionsService:
        return ActionsService(self._config, self._execution_context)

    @property
    def buckets(self) -> BucketsService:
        if not self._buckets_service:
            self._buckets_service = BucketsService(
                self._config, self._execution_context
            )
        return BucketsService(self._config, self._execution_context)

    @property
    def connections(self) -> ConnectionsService:
        if not self._connections_service:
            if not self._folders_service:
                self._folders_service = FolderService(
                    self._config, self._execution_context
                )
            self._connections_service = ConnectionsService(
                self._config, self._execution_context, self._folders_service
            )
        return self._connections_service

    @property
    def context_grounding(self) -> ContextGroundingService:
        if not self._folders_service:
            self._folders_service = FolderService(self._config, self._execution_context)
        if not self._buckets_service:
            self._buckets_service = BucketsService(
                self._config, self._execution_context
            )
        return ContextGroundingService(
            self._config,
            self._execution_context,
            self._folders_service,
            self._buckets_service,
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

    @property
    def folders(self) -> FolderService:
        if not self._folders_service:
            self._folders_service = FolderService(self._config, self._execution_context)
        return self._folders_service

    @property
    def llm_openai(self) -> UiPathOpenAIService:
        return UiPathOpenAIService(self._config, self._execution_context)

    @property
    def llm(self) -> UiPathLlmChatService:
        return UiPathLlmChatService(self._config, self._execution_context)

    @property
    def entities(self) -> EntitiesService:
        return EntitiesService(self._config, self._execution_context)
