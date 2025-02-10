from httpx import Response

from ._base_service import BaseService


class ProcessesService(BaseService):
    def invoke(self, release_key: str) -> Response:
        endpoint = (
            "/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.StartJobs"
        )
        content = str({"startInfo": {"ReleaseKey": release_key}})

        return self.request(
            "POST",
            endpoint,
            content=content,
        )

    @property
    def custom_headers(self) -> dict[str, str]:
        if self._config.folder_id is None:
            raise ValueError("Folder ID is required for Processes  Service")

        return {"x-uipath-organizationunitid": self._config.folder_id}
