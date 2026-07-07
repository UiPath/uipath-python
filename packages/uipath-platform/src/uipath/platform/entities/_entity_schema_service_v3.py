"""Schema-side operations for the v3 Data Fabric entities API (preview).

Mirrors the entity/choice-set lifecycle of the v1
:class:`~uipath.platform.entities._entity_schema_service.EntitySchemaService`,
targeting the ``datafabric_/api/v3/entities`` routes and returning the v3
schema models (:class:`EntityRecordV3`, :class:`CompositeEntityMetadataResponse`,
:class:`GetAllResponseV3`). Payload building and validation are reused from the
v1 service.
"""

from typing import Any, Dict, List, Optional

from ..common._base_service import BaseService
from ..common._config import UiPathApiConfig
from ..common._execution_context import UiPathExecutionContext
from ..common._models import Endpoint, RequestSpec
from ..orchestrator._folder_service import FolderService
from ._entity_schema_service import EntitySchemaService
from .entities import (
    EntityCreateFieldOptions,
    EntityCreateOptions,
    EntityMetadataUpdateOptions,
)
from .entities_v3 import (
    CompositeEntityMetadataResponse,
    EntityRecordV3,
    GetAllResponseV3,
)

_V3_BASE = "datafabric_/api/v3/entities"


class EntitySchemaServiceV3(BaseService):
    """HTTP service for v3 entity-schema operations.

    Backend target: ``datafabric_/api/v3/entities``.

    !!! warning "Preview Feature"
        This service is experimental. Behavior and parameters are subject to
        change in future versions.
    """

    def __init__(
        self,
        config: UiPathApiConfig,
        execution_context: UiPathExecutionContext,
        folders_service: Optional[FolderService] = None,
    ) -> None:
        """Initialise the v3 schema service."""
        super().__init__(config=config, execution_context=execution_context)
        self._folders_service = folders_service

    def retrieve(self, entity_id: str) -> EntityRecordV3:
        """v3 retrieve entity definition by id."""
        response = self.request("GET", Endpoint(f"{_V3_BASE}/{entity_id}"))
        return EntityRecordV3.model_validate(response.json())

    async def retrieve_async(self, entity_id: str) -> EntityRecordV3:
        """Async variant of :meth:`retrieve`."""
        response = await self.request_async("GET", Endpoint(f"{_V3_BASE}/{entity_id}"))
        return EntityRecordV3.model_validate(response.json())

    def retrieve_by_name(
        self, entity_name: str, folder_key: Optional[str] = None
    ) -> CompositeEntityMetadataResponse:
        """v3 retrieve entity metadata (composite-aware) by name."""
        headers = EntitySchemaService._folder_key_headers(folder_key)
        response = self.request(
            "GET", Endpoint(f"{_V3_BASE}/{entity_name}/metadata"), headers=headers
        )
        return CompositeEntityMetadataResponse.model_validate(response.json())

    async def retrieve_by_name_async(
        self, entity_name: str, folder_key: Optional[str] = None
    ) -> CompositeEntityMetadataResponse:
        """Async variant of :meth:`retrieve_by_name`."""
        headers = EntitySchemaService._folder_key_headers(folder_key)
        response = await self.request_async(
            "GET", Endpoint(f"{_V3_BASE}/{entity_name}/metadata"), headers=headers
        )
        return CompositeEntityMetadataResponse.model_validate(response.json())

    def list_entities(self) -> List[EntityRecordV3]:
        """v3 list all entity definitions."""
        response = self.request("GET", Endpoint(_V3_BASE))
        return [EntityRecordV3.model_validate(item) for item in response.json()]

    async def list_entities_async(self) -> List[EntityRecordV3]:
        """Async variant of :meth:`list_entities`."""
        response = await self.request_async("GET", Endpoint(_V3_BASE))
        return [EntityRecordV3.model_validate(item) for item in response.json()]

    def get_all(self, start: int = 0, limit: int = 1000) -> GetAllResponseV3:
        """v3 full schema catalog (entities + choice sets)."""
        response = self.request(
            "GET", Endpoint(f"{_V3_BASE}/all"), params={"start": start, "limit": limit}
        )
        return GetAllResponseV3.model_validate(response.json() or {})

    async def get_all_async(
        self, start: int = 0, limit: int = 1000
    ) -> GetAllResponseV3:
        """Async variant of :meth:`get_all`."""
        response = await self.request_async(
            "GET", Endpoint(f"{_V3_BASE}/all"), params={"start": start, "limit": limit}
        )
        return GetAllResponseV3.model_validate(response.json() or {})

    def create_entity(
        self,
        name: str,
        fields: List[EntityCreateFieldOptions],
        options: Optional[EntityCreateOptions] = None,
    ) -> str:
        """v3 create an entity (reuses v1 payload building + validation)."""
        spec = self._create_entity_spec(name, fields, options)
        response = self.request(spec.method, spec.endpoint, json=spec.json)
        return EntitySchemaService._extract_entity_id(response)

    async def create_entity_async(
        self,
        name: str,
        fields: List[EntityCreateFieldOptions],
        options: Optional[EntityCreateOptions] = None,
    ) -> str:
        """Async variant of :meth:`create_entity`."""
        spec = self._create_entity_spec(name, fields, options)
        response = await self.request_async(spec.method, spec.endpoint, json=spec.json)
        return EntitySchemaService._extract_entity_id(response)

    def delete_entity(self, entity_id: str) -> None:
        """v3 soft-delete an entity."""
        self.request("DELETE", Endpoint(f"{_V3_BASE}/{entity_id}"))

    async def delete_entity_async(self, entity_id: str) -> None:
        """Async variant of :meth:`delete_entity`."""
        await self.request_async("DELETE", Endpoint(f"{_V3_BASE}/{entity_id}"))

    def update_entity_metadata(
        self, entity_id: str, metadata: EntityMetadataUpdateOptions | Dict[str, Any]
    ) -> None:
        """v3 update entity metadata."""
        spec = self._update_metadata_spec(entity_id, metadata)
        self.request(spec.method, spec.endpoint, json=spec.json)

    async def update_entity_metadata_async(
        self, entity_id: str, metadata: EntityMetadataUpdateOptions | Dict[str, Any]
    ) -> None:
        """Async variant of :meth:`update_entity_metadata`."""
        spec = self._update_metadata_spec(entity_id, metadata)
        await self.request_async(spec.method, spec.endpoint, json=spec.json)

    # ------------------------------------------------------------------
    # Request-spec builders (reuse v1 payload building, v3 endpoints)
    # ------------------------------------------------------------------

    @staticmethod
    def _create_entity_spec(
        name: str,
        fields: List[EntityCreateFieldOptions],
        options: Optional[EntityCreateOptions] = None,
    ) -> RequestSpec:
        v1_spec = EntitySchemaService._create_entity_spec(name, fields, options)
        return RequestSpec(
            method="POST", endpoint=Endpoint(_V3_BASE), json=v1_spec.json
        )

    @staticmethod
    def _update_metadata_spec(
        entity_id: str, metadata: EntityMetadataUpdateOptions | Dict[str, Any]
    ) -> RequestSpec:
        if not isinstance(metadata, EntityMetadataUpdateOptions):
            metadata = EntityMetadataUpdateOptions.model_validate(metadata)
        body = metadata.model_dump(by_alias=True, exclude_none=True)
        return RequestSpec(
            method="PATCH",
            endpoint=Endpoint(f"{_V3_BASE}/{entity_id}/metadata"),
            json=body,
        )
