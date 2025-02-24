from os import environ as env
from typing import Optional

from dotenv import load_dotenv

from ._config import Config
from ._execution_context import ExecutionContext
from ._services import (
    ActionsService,
    ApiClient,
    AssetsService,
    BucketsService,
    ContextGroundingService,
    ProcessesService,
)
from ._utils import setup_logging

load_dotenv()


class UiPathSDK:
    def __init__(
        self,
        *,
        base_url: Optional[str] = None,
        secret: Optional[str] = None,
        debug: bool = False,
    ) -> None:
        base_url_value = base_url or env.get("UIPATH_URL")
        secret_value = (
            secret
            or env.get("UNATTENDED_USER_ACCESS_TOKEN")
            or env.get("UIPATH_ACCESS_TOKEN")
        )

        self._config = Config(
            base_url=base_url_value,  # type: ignore
            secret=secret_value,  # type: ignore
        )

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
    def context_grounding(self) -> ContextGroundingService:
        return ContextGroundingService(self._config, self._execution_context)
