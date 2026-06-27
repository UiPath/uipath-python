"""Ontology-side operations for the Data Fabric entities surface.

Handles retrieval of ontology component files (OWL schema, R2RML mapping, and
other typed files). Entity schema and record operations are managed by
:class:`EntitySchemaService` / :class:`EntityDataService` and exposed alongside
ontology operations through :class:`EntitiesService`.
"""

from typing import Any, Dict, Optional

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
    ontology_key: Optional[str] = Field(None, alias="referenceKey")
    folder_key: str = Field(alias="folderId")
    description: Optional[str] = None
    id: Optional[str] = None


class EntityOntologyService(BaseService):
    """HTTP service for Data Fabric ontology file retrieval.

    Backend target: ``datafabric_/api/ontologies``.

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

    async def get_file_async(
        self,
        ontology_name: str,
        file_type: str = "owl",
        folder_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Internal implementation; see :meth:`EntitiesService.get_ontology_file_async`."""
        spec = self._ontology_file_spec(ontology_name, file_type, folder_key)
        response = await self.request_async(
            spec.method, spec.endpoint, headers=spec.headers
        )
        return response.json()

    @staticmethod
    def _ontology_file_spec(
        ontology_name: str, file_type: str, folder_key: Optional[str] = None
    ) -> RequestSpec:
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(
                f"datafabric_/api/ontologies/{ontology_name}/files/{file_type}"
            ),
            headers=header_folder(folder_key, None),
        )
