from logging import getLogger
from os import environ as env

from dotenv import load_dotenv

from ._config import Config
from ._execution_context import ExecutionContext
from ._services.assets_service import AssetsService
from ._services.processes_service import ProcessesService
from ._utils._logs import setup_logging

load_dotenv()


class UiPathSDK:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        secret: str | None = None,
        debug: bool = False,
    ) -> None:
        base_url_value = base_url or env.get("UIPATH_URL")
        secret_value = (
            secret
            or env.get("UNATTENDED_USER_ACCESS_TOKEN")
            or env.get("UIPATH_ACCESS_TOKEN")
        )
        folder_id_value = env.get("UIPATH_FOLDER_ID")

        self._config = Config(
            base_url=base_url_value,  # type: ignore
            secret=secret_value,  # type: ignore
            folder_id=folder_id_value,
            debug=debug,
        )

        setup_logging(self._config.debug)
        log = getLogger("uipath")

        log.debug("CONFIG:")
        log.debug(f"{self._config.model_dump()}\n")

        self._execution_context = ExecutionContext()

    @property
    def assets(self) -> AssetsService:
        return AssetsService(self._config, self._execution_context)

    @property
    def processes(self) -> ProcessesService:
        return ProcessesService(self._config, self._execution_context)
