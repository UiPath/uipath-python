"""Public facade for the v3 Data Fabric entities API (preview).

:class:`EntitiesServiceV3` exposes the same operation set as the v1
:class:`~uipath.platform.entities._entities_service.EntitiesService`, but routes
to the ``datafabric_/api/v3/entities/...`` endpoints and returns the v3 response
models (:class:`EntityWriteResponseV3`, :class:`QueryResponseV3`,
:class:`BatchOperationResponse`, :class:`EntityRecordV3`, ...).

Reach it via ``sdk.entities_v3``. ``sdk.entities`` (v1) is unchanged.

Notes:
    * ``entity_key`` is used as the v3 ``{entityName}`` path segment.
    * :meth:`query_entity_records` (federated SQL) is version-agnostic and runs
      through the shared ``/api/v1/query/execute`` engine.
    * :meth:`import_records` (CSV bulk upload) has no v3 equivalent and raises
      :class:`NotImplementedError`.
"""

import logging
from typing import Any, Dict, List, Optional

from uipath.core.tracing import traced

from ..common._base_service import BaseService
from ..common._config import UiPathApiConfig
from ..common._execution_context import UiPathExecutionContext
from ..errors._datafabric_error import attach_datafabric_error_mapping
from ..orchestrator._folder_service import FolderService
from ._entity_data_service import EntityDataService, FileContent
from ._entity_data_service_v3 import EntityDataServiceV3
from ._entity_resolution import create_routing_strategy
from ._entity_schema_service_v3 import EntitySchemaServiceV3
from .entities import (
    ChoiceSetValue,
    EntityAggregate,
    EntityBinning,
    EntityCreateFieldOptions,
    EntityCreateOptions,
    EntityJoin,
    EntityMetadataUpdateOptions,
    EntityQueryFilterGroup,
    EntityQuerySortOption,
    QueryRoutingOverrideContext,
)
from .entities_v3 import (
    BatchOperationResponse,
    CompositeEntityMetadataResponse,
    EntityRecordV3,
    EntityWriteResponseV3,
    GetAllResponseV3,
    QueryResponseV3,
)

logger = logging.getLogger(__name__)


class EntitiesServiceV3(BaseService):
    """Service for UiPath Data Service entities using the **v3** API (preview).

    !!! warning "Preview Feature"
        This service is experimental. Behavior and parameters are subject to
        change in future versions.
    """

    def __init__(
        self,
        config: UiPathApiConfig,
        execution_context: UiPathExecutionContext,
        folders_service: Optional[FolderService] = None,
        folders_map: Optional[Dict[str, str]] = None,
        entity_name_overrides: Optional[Dict[str, str]] = None,
        routing_context: Optional[QueryRoutingOverrideContext] = None,
    ) -> None:
        """Initialise the v3 facade and its underlying schema and data services."""
        super().__init__(config=config, execution_context=execution_context)
        self._folders_service = folders_service
        self._routing_strategy = create_routing_strategy(
            folders_map=folders_map,
            effective_entity_names=entity_name_overrides,
            routing_context=routing_context,
            folders_service=folders_service,
        )
        self._schema = EntitySchemaServiceV3(
            config=config,
            execution_context=execution_context,
            folders_service=folders_service,
        )
        self._data = EntityDataServiceV3(
            config=config,
            execution_context=execution_context,
            folders_service=folders_service,
            routing_strategy=self._routing_strategy,
        )
        # Federated SQL is version-agnostic; delegate to the shared v1 engine.
        self._federated = EntityDataService(
            config=config,
            execution_context=execution_context,
            folders_service=folders_service,
            routing_strategy=self._routing_strategy,
        )

    # ------------------------------------------------------------------
    # Schema operations
    # ------------------------------------------------------------------

    @traced(name="entity_retrieve", run_type="uipath")
    def retrieve(self, entity_id: str) -> EntityRecordV3:
        """Retrieve an entity definition by id (v3)."""
        return self._schema.retrieve(entity_id)

    @traced(name="entity_retrieve", run_type="uipath")
    async def retrieve_async(self, entity_id: str) -> EntityRecordV3:
        """Async variant of :meth:`retrieve`."""
        return await self._schema.retrieve_async(entity_id)

    @traced(name="entity_retrieve_by_name", run_type="uipath")
    def retrieve_by_name(
        self, entity_name: str, folder_key: Optional[str] = None
    ) -> CompositeEntityMetadataResponse:
        """Retrieve composite-aware entity metadata by name (v3)."""
        return self._schema.retrieve_by_name(entity_name, folder_key=folder_key)

    @traced(name="entity_retrieve_by_name", run_type="uipath")
    async def retrieve_by_name_async(
        self, entity_name: str, folder_key: Optional[str] = None
    ) -> CompositeEntityMetadataResponse:
        """Async variant of :meth:`retrieve_by_name`."""
        return await self._schema.retrieve_by_name_async(
            entity_name, folder_key=folder_key
        )

    @traced(name="list_entities", run_type="uipath")
    def list_entities(self) -> List[EntityRecordV3]:
        """List all entity definitions (v3)."""
        return self._schema.list_entities()

    @traced(name="list_entities", run_type="uipath")
    async def list_entities_async(self) -> List[EntityRecordV3]:
        """Async variant of :meth:`list_entities`."""
        return await self._schema.list_entities_async()

    @traced(name="list_choicesets", run_type="uipath")
    def list_choicesets(self) -> List[Dict[str, Any]]:
        """List all choice sets (v3, via the ``/all`` catalog)."""
        return self._schema.get_all().choicesets

    @traced(name="list_choicesets", run_type="uipath")
    async def list_choicesets_async(self) -> List[Dict[str, Any]]:
        """Async variant of :meth:`list_choicesets`."""
        return (await self._schema.get_all_async()).choicesets

    @traced(name="entity_get_all", run_type="uipath")
    def get_all(self, start: int = 0, limit: int = 1000) -> GetAllResponseV3:
        """Return the full schema catalog — entities and choice sets (v3)."""
        return self._schema.get_all(start=start, limit=limit)

    @traced(name="entity_get_all", run_type="uipath")
    async def get_all_async(
        self, start: int = 0, limit: int = 1000
    ) -> GetAllResponseV3:
        """Async variant of :meth:`get_all`."""
        return await self._schema.get_all_async(start=start, limit=limit)

    @traced(name="entity_create", run_type="uipath")
    def create_entity(
        self,
        name: str,
        fields: List[EntityCreateFieldOptions],
        options: Optional[EntityCreateOptions] = None,
    ) -> str:
        """Create a new entity and return its id (v3)."""
        return self._schema.create_entity(name, fields, options)

    @traced(name="entity_create", run_type="uipath")
    async def create_entity_async(
        self,
        name: str,
        fields: List[EntityCreateFieldOptions],
        options: Optional[EntityCreateOptions] = None,
    ) -> str:
        """Async variant of :meth:`create_entity`."""
        return await self._schema.create_entity_async(name, fields, options)

    @traced(name="entity_delete", run_type="uipath")
    def delete_entity(self, entity_id: str) -> None:
        """Delete an entity and all of its records (v3)."""
        self._schema.delete_entity(entity_id)

    @traced(name="entity_delete", run_type="uipath")
    async def delete_entity_async(self, entity_id: str) -> None:
        """Async variant of :meth:`delete_entity`."""
        await self._schema.delete_entity_async(entity_id)

    @traced(name="entity_update_metadata", run_type="uipath")
    def update_entity_metadata(
        self, entity_id: str, metadata: EntityMetadataUpdateOptions | Dict[str, Any]
    ) -> None:
        """Update an entity's display name, description, and/or RBAC flag (v3)."""
        self._schema.update_entity_metadata(entity_id, metadata)

    @traced(name="entity_update_metadata", run_type="uipath")
    async def update_entity_metadata_async(
        self, entity_id: str, metadata: EntityMetadataUpdateOptions | Dict[str, Any]
    ) -> None:
        """Async variant of :meth:`update_entity_metadata`."""
        await self._schema.update_entity_metadata_async(entity_id, metadata)

    # ------------------------------------------------------------------
    # Data operations
    # ------------------------------------------------------------------

    @traced(name="get_choiceset_values", run_type="uipath")
    def get_choiceset_values(
        self,
        choiceset_id: str,
        start: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[ChoiceSetValue]:
        """Get the values of a choice set by id (v3)."""
        return self._data.get_choiceset_values(choiceset_id, start=start, limit=limit)

    @traced(name="get_choiceset_values", run_type="uipath")
    async def get_choiceset_values_async(
        self,
        choiceset_id: str,
        start: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[ChoiceSetValue]:
        """Async variant of :meth:`get_choiceset_values`."""
        return await self._data.get_choiceset_values_async(
            choiceset_id, start=start, limit=limit
        )

    @traced(name="entity_list_records", run_type="uipath")
    def list_records(
        self,
        entity_key: str,
        start: int = 0,
        limit: int = 100,
        expansion_level: Optional[int] = None,
    ) -> QueryResponseV3:
        """Read a page of records from an entity (v3).

        v3 paged read supports ``start`` / ``limit`` / ``expansion_level`` only;
        for filtering, sorting, and projection use :meth:`retrieve_records`.
        """
        return self._data.list_records(
            entity_key, start=start, limit=limit, expansion_level=expansion_level
        )

    @traced(name="entity_list_records", run_type="uipath")
    async def list_records_async(
        self,
        entity_key: str,
        start: int = 0,
        limit: int = 100,
        expansion_level: Optional[int] = None,
    ) -> QueryResponseV3:
        """Async variant of :meth:`list_records`."""
        return await self._data.list_records_async(
            entity_key, start=start, limit=limit, expansion_level=expansion_level
        )

    @traced(name="entity_insert_record", run_type="uipath")
    def insert_record(
        self, entity_key: str, data: Any, expansion_level: Optional[int] = None
    ) -> EntityWriteResponseV3:
        """Insert a single record (v3)."""
        return self._data.insert_record(
            entity_key, data, expansion_level=expansion_level
        )

    @traced(name="entity_insert_record", run_type="uipath")
    async def insert_record_async(
        self, entity_key: str, data: Any, expansion_level: Optional[int] = None
    ) -> EntityWriteResponseV3:
        """Async variant of :meth:`insert_record`."""
        return await self._data.insert_record_async(
            entity_key, data, expansion_level=expansion_level
        )

    @traced(name="entity_get_record", run_type="uipath")
    def get_record(
        self, entity_key: str, record_id: str, expansion_level: Optional[int] = None
    ) -> EntityWriteResponseV3:
        """Fetch a single record by id (v3)."""
        return self._data.get_record(
            entity_key, record_id, expansion_level=expansion_level
        )

    @traced(name="entity_get_record", run_type="uipath")
    async def get_record_async(
        self, entity_key: str, record_id: str, expansion_level: Optional[int] = None
    ) -> EntityWriteResponseV3:
        """Async variant of :meth:`get_record`."""
        return await self._data.get_record_async(
            entity_key, record_id, expansion_level=expansion_level
        )

    @traced(name="entity_update_record", run_type="uipath")
    def update_record(
        self,
        entity_key: str,
        record_id: str,
        data: Any,
        expansion_level: Optional[int] = None,
    ) -> EntityWriteResponseV3:
        """Update a single record by id (v3)."""
        return self._data.update_record(
            entity_key, record_id, data, expansion_level=expansion_level
        )

    @traced(name="entity_update_record", run_type="uipath")
    async def update_record_async(
        self,
        entity_key: str,
        record_id: str,
        data: Any,
        expansion_level: Optional[int] = None,
    ) -> EntityWriteResponseV3:
        """Async variant of :meth:`update_record`."""
        return await self._data.update_record_async(
            entity_key, record_id, data, expansion_level=expansion_level
        )

    @traced(name="entity_delete_record", run_type="uipath")
    def delete_record(self, entity_key: str, record_id: str) -> EntityWriteResponseV3:
        """Delete a single record by id (v3)."""
        return self._data.delete_record(entity_key, record_id)

    @traced(name="entity_delete_record", run_type="uipath")
    async def delete_record_async(
        self, entity_key: str, record_id: str
    ) -> EntityWriteResponseV3:
        """Async variant of :meth:`delete_record`."""
        return await self._data.delete_record_async(entity_key, record_id)

    @traced(name="entity_record_insert_batch", run_type="uipath")
    def insert_records(
        self,
        entity_key: str,
        records: List[Any],
        expansion_level: Optional[int] = None,
        fail_on_first: Optional[bool] = None,
    ) -> BatchOperationResponse:
        """Insert multiple records in a single batch (v3)."""
        return self._data.insert_records(
            entity_key,
            records,
            expansion_level=expansion_level,
            fail_on_first=fail_on_first,
        )

    @traced(name="entity_record_insert_batch", run_type="uipath")
    async def insert_records_async(
        self,
        entity_key: str,
        records: List[Any],
        expansion_level: Optional[int] = None,
        fail_on_first: Optional[bool] = None,
    ) -> BatchOperationResponse:
        """Async variant of :meth:`insert_records`."""
        return await self._data.insert_records_async(
            entity_key,
            records,
            expansion_level=expansion_level,
            fail_on_first=fail_on_first,
        )

    @traced(name="entity_record_update_batch", run_type="uipath")
    def update_records(
        self,
        entity_key: str,
        records: List[Any],
        expansion_level: Optional[int] = None,
        fail_on_first: Optional[bool] = None,
    ) -> BatchOperationResponse:
        """Update multiple records in a single batch (v3)."""
        return self._data.update_records(
            entity_key,
            records,
            expansion_level=expansion_level,
            fail_on_first=fail_on_first,
        )

    @traced(name="entity_record_update_batch", run_type="uipath")
    async def update_records_async(
        self,
        entity_key: str,
        records: List[Any],
        expansion_level: Optional[int] = None,
        fail_on_first: Optional[bool] = None,
    ) -> BatchOperationResponse:
        """Async variant of :meth:`update_records`."""
        return await self._data.update_records_async(
            entity_key,
            records,
            expansion_level=expansion_level,
            fail_on_first=fail_on_first,
        )

    @traced(name="entity_record_delete_batch", run_type="uipath")
    def delete_records(
        self,
        entity_key: str,
        record_ids: List[str],
        fail_on_first: Optional[bool] = None,
    ) -> BatchOperationResponse:
        """Delete multiple records by id in a single batch (v3)."""
        return self._data.delete_records(
            entity_key, record_ids, fail_on_first=fail_on_first
        )

    @traced(name="entity_record_delete_batch", run_type="uipath")
    async def delete_records_async(
        self,
        entity_key: str,
        record_ids: List[str],
        fail_on_first: Optional[bool] = None,
    ) -> BatchOperationResponse:
        """Async variant of :meth:`delete_records`."""
        return await self._data.delete_records_async(
            entity_key, record_ids, fail_on_first=fail_on_first
        )

    @traced(name="entity_retrieve_records", run_type="uipath")
    def retrieve_records(
        self,
        entity_key: str,
        filter_group: Optional[EntityQueryFilterGroup] = None,
        sort_options: Optional[List[EntityQuerySortOption]] = None,
        selected_fields: Optional[List[str]] = None,
        expansions: Optional[List[Any]] = None,
        expansion_level: Optional[int] = None,
        aggregates: Optional[List[EntityAggregate]] = None,
        group_by: Optional[List[str]] = None,
        joins: Optional[List[EntityJoin]] = None,
        binnings: Optional[List[EntityBinning]] = None,
        start: Optional[int] = None,
        limit: Optional[int] = None,
        child_limit: Optional[int] = None,
    ) -> QueryResponseV3:
        """Retrieve records with structured filters, sorting, and aggregates (v3).

        ``child_limit`` bounds the per-parent child rows returned for composite
        entities (v3-only).
        """
        return self._data.retrieve_records(
            entity_key,
            filter_group=filter_group,
            sort_options=sort_options,
            selected_fields=selected_fields,
            expansions=expansions,
            expansion_level=expansion_level,
            aggregates=aggregates,
            group_by=group_by,
            joins=joins,
            binnings=binnings,
            start=start,
            limit=limit,
            child_limit=child_limit,
        )

    @traced(name="entity_retrieve_records", run_type="uipath")
    async def retrieve_records_async(
        self,
        entity_key: str,
        filter_group: Optional[EntityQueryFilterGroup] = None,
        sort_options: Optional[List[EntityQuerySortOption]] = None,
        selected_fields: Optional[List[str]] = None,
        expansions: Optional[List[Any]] = None,
        expansion_level: Optional[int] = None,
        aggregates: Optional[List[EntityAggregate]] = None,
        group_by: Optional[List[str]] = None,
        joins: Optional[List[EntityJoin]] = None,
        binnings: Optional[List[EntityBinning]] = None,
        start: Optional[int] = None,
        limit: Optional[int] = None,
        child_limit: Optional[int] = None,
    ) -> QueryResponseV3:
        """Async variant of :meth:`retrieve_records`."""
        return await self._data.retrieve_records_async(
            entity_key,
            filter_group=filter_group,
            sort_options=sort_options,
            selected_fields=selected_fields,
            expansions=expansions,
            expansion_level=expansion_level,
            aggregates=aggregates,
            group_by=group_by,
            joins=joins,
            binnings=binnings,
            start=start,
            limit=limit,
            child_limit=child_limit,
        )

    @attach_datafabric_error_mapping("query_entity_records")
    @traced(name="entity_query_records", run_type="uipath")
    def query_entity_records(self, sql_query: str) -> List[Dict[str, Any]]:
        """Query entity records using a validated SQL query (version-agnostic)."""
        return self._federated.query_entity_records(sql_query)

    @attach_datafabric_error_mapping("query_entity_records_async")
    @traced(name="entity_query_records", run_type="uipath")
    async def query_entity_records_async(self, sql_query: str) -> List[Dict[str, Any]]:
        """Async variant of :meth:`query_entity_records`."""
        return await self._federated.query_entity_records_async(sql_query)

    @traced(name="entity_upload_attachment", run_type="uipath")
    def upload_attachment(
        self,
        entity_id: str,
        record_id: str,
        field_name: str,
        file: Optional[FileContent] = None,
        file_path: Optional[str] = None,
        expansion_level: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Upload a file attachment to a File-type field on a record (v3)."""
        return self._data.upload_attachment(
            entity_id,
            record_id,
            field_name,
            file=file,
            file_path=file_path,
            expansion_level=expansion_level,
        )

    @traced(name="entity_upload_attachment", run_type="uipath")
    async def upload_attachment_async(
        self,
        entity_id: str,
        record_id: str,
        field_name: str,
        file: Optional[FileContent] = None,
        file_path: Optional[str] = None,
        expansion_level: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Async variant of :meth:`upload_attachment`."""
        return await self._data.upload_attachment_async(
            entity_id,
            record_id,
            field_name,
            file=file,
            file_path=file_path,
            expansion_level=expansion_level,
        )

    @traced(name="entity_download_attachment", run_type="uipath")
    def download_attachment(
        self, entity_id: str, record_id: str, field_name: str
    ) -> bytes:
        """Download a file attached to a record (v3)."""
        return self._data.download_attachment(entity_id, record_id, field_name)

    @traced(name="entity_download_attachment", run_type="uipath")
    async def download_attachment_async(
        self, entity_id: str, record_id: str, field_name: str
    ) -> bytes:
        """Async variant of :meth:`download_attachment`."""
        return await self._data.download_attachment_async(
            entity_id, record_id, field_name
        )

    @traced(name="entity_delete_attachment", run_type="uipath")
    def delete_attachment(
        self,
        entity_id: str,
        record_id: str,
        field_name: str,
        expansion_level: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Remove the file attached to a File-type field on a record (v3)."""
        return self._data.delete_attachment(
            entity_id, record_id, field_name, expansion_level=expansion_level
        )

    @traced(name="entity_delete_attachment", run_type="uipath")
    async def delete_attachment_async(
        self,
        entity_id: str,
        record_id: str,
        field_name: str,
        expansion_level: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Async variant of :meth:`delete_attachment`."""
        return await self._data.delete_attachment_async(
            entity_id, record_id, field_name, expansion_level=expansion_level
        )

    def import_records(self, *args: Any, **kwargs: Any) -> Any:
        """Not available in v3 — CSV bulk import has no v3 endpoint.

        Use ``sdk.entities.import_records`` (v1) instead.
        """
        raise NotImplementedError(
            "CSV bulk import is not available in the Entities v3 API; "
            "use sdk.entities.import_records (v1)."
        )

    async def import_records_async(self, *args: Any, **kwargs: Any) -> Any:
        """Not available in v3 — see :meth:`import_records`."""
        raise NotImplementedError(
            "CSV bulk import is not available in the Entities v3 API; "
            "use sdk.entities.import_records_async (v1)."
        )
