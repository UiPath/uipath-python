from httpx import Client, Headers

from ._assets_service import RobotAssetsService
from ._processes_service import ProcessesService
from ._uipath_client_config import UiPathClientConfig


class UiPathClient:
    def __init__(self, secret: str | None) -> None:
        self.config = UiPathClientConfig()

        if secret is not None:
            self.config.secret = secret

        if self.config.secret is None:
            raise ValueError("Secret is required")

        self._init_http_client()
        self._init_services()

    def change_folder(self, folder_id: str) -> None:
        self.config.folder_id = folder_id
        self._init_http_client()
        self._init_services()

    def _init_http_client(self) -> None:
        headers = Headers(
            {
                k: v
                for k, v in {
                    "Authorization": f"Bearer {self.config.secret}",
                    "Content-Type": "application/json",
                    "x-uipath-organizationunitid": self.config.folder_id,
                }.items()
                if v is not None
            }
        )
        self._http_client = Client(base_url=self.config.base_url, headers=headers)

    def _init_services(self) -> None:
        self.robot_assets = RobotAssetsService(self._http_client)
        self.processes = ProcessesService(self._http_client)
