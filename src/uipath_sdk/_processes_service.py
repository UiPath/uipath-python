from httpx import Response

from ._base_service import BaseService


class ProcessesService(BaseService):
    def invoke_process(self, release_key: str) -> Response:
        return self.client.post(
            "/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.StartJobs",
            content=str({"startInfo": {"ReleaseKey": release_key}}),
        )
