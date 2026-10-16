"""Ontology-side operations for the Data Fabric entities surface.

Handles retrieval of ontology component files ("artifacts": the OWL schema, the
mapping, and other typed files) from the Ontology service. Entity schema and record operations are managed by
`EntitySchemaService` / `EntityDataService` and exposed alongside
ontology operations through `EntitiesService`.
"""

from typing import Any, Dict, List, Optional
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict, Field

from ..common._base_service import BaseService
from ..common._config import UiPathApiConfig
from ..common._execution_context import UiPathExecutionContext
from ..common._folder_context import header_folder
from ..common._models import Endpoint, RequestSpec
from ..orchestrator._folder_service import FolderService


class DataFabricOntologyItem(BaseModel):
    """A single Data Fabric ontology reference from agent configuration."""

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )

    name: str
    folder_key: str = Field(alias="folderId")
    description: Optional[str] = None
    id: Optional[str] = None


# Legacy Data Fabric file names -> Ontology-service artifact types.
_LEGACY_FILE_TYPES = {"owl": "schema", "r2rml": "mapping", "shacl": "constraints"}


class EntityOntologyService(BaseService):
    """HTTP service for ontology artifact retrieval.

    Backend target: ``ontology_/api/v1/ontology/{ontology}/artifact``.

    See Also:
        https://docs.uipath.com/data-service/automation-cloud/latest/user-guide/introduction

    !!! warning "Preview Feature"
        This service is currently experimental. Behavior and parameters are
        subject to change in future versions.
    """

    def __init__(
        self,
        config: UiPathApiConfig,
        execution_context: UiPathExecutionContext,
        folders_service: Optional[FolderService] = None,
    ) -> None:
        """Initialise the ontology service."""
        super().__init__(config=config, execution_context=execution_context)
        self._folders_service = folders_service

    async def list_artifacts_async(
        self,
        ontology_name: str,
        artifact_type: Optional[str] = None,
        folder_key: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Internal implementation; see :meth:`EntitiesService.list_ontology_artifacts_async`."""
        spec = self._list_spec(ontology_name, artifact_type, folder_key)
        response = await self.request_async(
            spec.method, spec.endpoint, params=spec.params, headers=spec.headers
        )
        return response.json()

    async def get_file_async(
        self,
        ontology_name: str,
        file_type: str = "owl",
        folder_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Internal implementation; see :meth:`EntitiesService.get_ontology_file_async`."""
        artifact_type = _LEGACY_FILE_TYPES.get(file_type, file_type)
        artifacts = await self.list_artifacts_async(
            ontology_name, artifact_type, folder_key
        )
        if not artifacts:
            raise ValueError(
                f"Ontology '{ontology_name}' has no '{artifact_type}' artifact."
            )
        contents: List[str] = []
        media_type = ""
        for artifact in artifacts:
            spec = self._download_spec(ontology_name, artifact["fileName"], folder_key)
            response = await self.request_async(
                spec.method, spec.endpoint, headers=spec.headers
            )
            contents.append(response.text)
            media_type = media_type or response.headers.get("content-type", "")
        return {"content": "\n\n".join(contents), "mediaType": media_type}

    @staticmethod
    def _list_spec(
        ontology_name: str,
        artifact_type: Optional[str] = None,
        folder_key: Optional[str] = None,
    ) -> RequestSpec:
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(f"ontology_/api/v1/ontology/{ontology_name}/artifact"),
            params={"type": artifact_type} if artifact_type else {},
            headers=header_folder(folder_key, None),
        )

    @staticmethod
    def _download_spec(
        ontology_name: str, file_name: str, folder_key: Optional[str] = None
    ) -> RequestSpec:
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(
                f"ontology_/api/v1/ontology/{ontology_name}/artifact/{quote(file_name, safe='')}"
            ),
            headers=header_folder(folder_key, None),
        )
