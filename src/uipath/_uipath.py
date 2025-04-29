from os import environ as env
from typing import Optional

from dotenv import load_dotenv
from pydantic import ValidationError

from ._config import Config
from ._execution_context import ExecutionContext
from ._services import (
    ActionsService,
    ApiClient,
    AssetsService,
    BucketsService,
    ConnectionsService,
    ContextGroundingService,
    FolderService,
    JobsService,
    ProcessesService,
    QueuesService,
)
from ._utils import setup_logging
from ._utils.constants import (
    ENV_BASE_URL,
    ENV_UIPATH_ACCESS_TOKEN,
    ENV_UNATTENDED_USER_ACCESS_TOKEN,
)
from .models.errors import BaseUrlMissingError, SecretMissingError

load_dotenv()


class UiPath:
    def __init__(
        self,
        *,
        base_url: Optional[str] = None,
        secret: Optional[str] = None,
        debug: bool = False,
    ) -> None:
        base_url_value = base_url or env.get(ENV_BASE_URL)
        secret_value = (
            secret
            or env.get(ENV_UNATTENDED_USER_ACCESS_TOKEN)
            or env.get(ENV_UIPATH_ACCESS_TOKEN)
        )

        try:
            self._config = Config(
                base_url=base_url_value,  # type: ignore
                secret=secret_value,  # type: ignore
            )
        except ValidationError as e:
            for error in e.errors():
                if error["loc"][0] == "base_url":
                    raise BaseUrlMissingError() from e
                elif error["loc"][0] == "secret":
                    raise SecretMissingError() from e
        self._folders_service: Optional[FolderService] = None

        setup_logging(debug)
        self._execution_context = ExecutionContext()

    @property
    def api_client(self) -> ApiClient:
        return ApiClient(self._config, self._execution_context)

    @property
    def assets(self) -> AssetsService:
        return AssetsService(self._config, self._execution_context)

    @property
    def processes(self) -> ProcessesService:
        return ProcessesService(self._config, self._execution_context)

    @property
    def actions(self) -> ActionsService:
        return ActionsService(self._config, self._execution_context)

    @property
    def buckets(self) -> BucketsService:
        return BucketsService(self._config, self._execution_context)

    @property
    def connections(self) -> ConnectionsService:
        return ConnectionsService(self._config, self._execution_context)

    @property
    def context_grounding(self) -> ContextGroundingService:
        if not self._folders_service:
            self._folders_service = FolderService(self._config, self._execution_context)
        return ContextGroundingService(
            self._config, self._execution_context, self._folders_service
        )

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
