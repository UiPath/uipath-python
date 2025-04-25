from typing import Optional

from uipath.tracing._traced import traced

from .._config import Config
from .._execution_context import ExecutionContext
from .._utils import Endpoint, RequestSpec
from ._base_service import BaseService


def _retrieve_spec(folder_path: str) -> RequestSpec:
    folder_name = folder_path.split("/")[-1]
    return RequestSpec(
        method="GET",
        endpoint=Endpoint(
            "orchestrator_/api/FoldersNavigation/GetFoldersForCurrentUser"
        ),
        params={
            "searchText": folder_name,
            "take": 1,
        },
    )


class FolderService(BaseService):
    """Service for managing UiPath Folders.

    A folder represents a single area for data organization
    and access control - it is created when you need to categorize, manage, and enforce authorization rules for a group
    of UiPath resources (i.e. processes, assets, connections, storage buckets etc.) or other folders
    """

    def __init__(self, config: Config, execution_context: ExecutionContext) -> None:
        super().__init__(config=config, execution_context=execution_context)

    @traced(name="folder_retrieve_key_by_folder_path", run_type="uipath")
    def retrieve_key_by_folder_path(self, folder_path: str) -> Optional[str]:
        spec = _retrieve_spec(folder_path)
        response = self.request(
            spec.method,
            url=spec.endpoint,
            params=spec.params,
        ).json()

        return next(
            (
                item["Key"]
                for item in response["PageItems"]
                if item["FullyQualifiedName"] == folder_path
            ),
            None,
        )
