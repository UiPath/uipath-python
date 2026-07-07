"""Data-side operations for the v3 Data Fabric entities API (preview).

Mirrors the record CRUD / query / attachment operations of the v1
:class:`~uipath.platform.entities._entity_data_service.EntityDataService`, but
targets the ``datafabric_/api/v3/entities/{entityName}/...`` routes and returns
the v3 response models (:class:`EntityWriteResponseV3`, :class:`QueryResponseV3`,
:class:`BatchOperationResponse`). Query-body assembly, record normalisation, and
file handling are reused from the v1 service.
"""

import logging
from typing import Any, Dict, List, Optional

from ..common._base_service import BaseService
from ..common._config import UiPathApiConfig
from ..common._execution_context import UiPathExecutionContext
from ..common._models import Endpoint, RequestSpec
from ..orchestrator._folder_service import FolderService
from ._entity_data_service import EntityDataService, FileContent, build_query_body
from ._entity_resolution import RoutingStrategy, create_routing_strategy
from .entities import (
    ChoiceSetValue,
    EntityAggregate,
    EntityBinning,
    EntityJoin,
    EntityQueryFilterGroup,
    EntityQuerySortOption,
    QueryRoutingOverrideContext,
)
from .entities_v3 import (
    BatchOperationResponse,
    EntityWriteResponseV3,
    QueryResponseV3,
)

logger = logging.getLogger(__name__)

_V3_BASE = "datafabric_/api/v3/entities"


class EntityDataServiceV3(BaseService):
    """HTTP service for v3 entity-record and attachment operations.

    Backend target: ``datafabric_/api/v3/entities/{entityName}/...``. The
    ``entity_key`` argument is used as the ``{entityName}`` path segment (v3
    name-based routing).

    !!! warning "Preview Feature"
        This service is experimental. Behavior and parameters are subject to
        change in future versions.
    """

    def __init__(
        self,
        config: UiPathApiConfig,
        execution_context: UiPathExecutionContext,
        folders_service: Optional[FolderService] = None,
        routing_strategy: Optional[RoutingStrategy] = None,
        folders_map: Optional[Dict[str, str]] = None,
        entity_name_overrides: Optional[Dict[str, str]] = None,
        routing_context: Optional[QueryRoutingOverrideContext] = None,
    ) -> None:
        """Initialise the v3 data service."""
        super().__init__(config=config, execution_context=execution_context)
        self._folders_service = folders_service
        self._routing_strategy: RoutingStrategy = (
            routing_strategy
            if routing_strategy is not None
            else create_routing_strategy(
                folders_map=folders_map,
                effective_entity_names=entity_name_overrides,
                routing_context=routing_context,
                folders_service=folders_service,
            )
        )

    # ------------------------------------------------------------------
    # Choice-set value lookup
    # ------------------------------------------------------------------

    def get_choiceset_values(
        self,
        choiceset_id: str,
        start: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[ChoiceSetValue]:
        """v3 choice-set values; see :meth:`EntitiesServiceV3.get_choiceset_values`."""
        spec = self._choiceset_values_spec(choiceset_id, start=start, limit=limit)
        response = self.request(spec.method, spec.endpoint, json=spec.json)
        return EntityDataService._parse_choiceset_values(response)

    async def get_choiceset_values_async(
        self,
        choiceset_id: str,
        start: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[ChoiceSetValue]:
        """Async variant of :meth:`get_choiceset_values`."""
        spec = self._choiceset_values_spec(choiceset_id, start=start, limit=limit)
        response = await self.request_async(spec.method, spec.endpoint, json=spec.json)
        return EntityDataService._parse_choiceset_values(response)

    # ------------------------------------------------------------------
    # List records (paged read)
    # ------------------------------------------------------------------

    def list_records(
        self,
        entity_key: str,
        start: int = 0,
        limit: int = 100,
        expansion_level: Optional[int] = None,
    ) -> QueryResponseV3:
        """v3 paged read; see :meth:`EntitiesServiceV3.list_records`."""
        spec = self._read_spec(entity_key, start, limit, expansion_level)
        response = self.request(spec.method, spec.endpoint, params=spec.params)
        return QueryResponseV3.model_validate(response.json() or {})

    async def list_records_async(
        self,
        entity_key: str,
        start: int = 0,
        limit: int = 100,
        expansion_level: Optional[int] = None,
    ) -> QueryResponseV3:
        """Async variant of :meth:`list_records`."""
        spec = self._read_spec(entity_key, start, limit, expansion_level)
        response = await self.request_async(
            spec.method, spec.endpoint, params=spec.params
        )
        return QueryResponseV3.model_validate(response.json() or {})

    # ------------------------------------------------------------------
    # Single-record operations
    # ------------------------------------------------------------------

    def insert_record(
        self, entity_key: str, data: Any, expansion_level: Optional[int] = None
    ) -> EntityWriteResponseV3:
        """v3 single insert; see :meth:`EntitiesServiceV3.insert_record`."""
        spec = self._write_spec(f"{entity_key}/insert", data, expansion_level)
        response = self.request(
            spec.method, spec.endpoint, params=spec.params, json=spec.json
        )
        return EntityWriteResponseV3.model_validate(response.json())

    async def insert_record_async(
        self, entity_key: str, data: Any, expansion_level: Optional[int] = None
    ) -> EntityWriteResponseV3:
        """Async variant of :meth:`insert_record`."""
        spec = self._write_spec(f"{entity_key}/insert", data, expansion_level)
        response = await self.request_async(
            spec.method, spec.endpoint, params=spec.params, json=spec.json
        )
        return EntityWriteResponseV3.model_validate(response.json())

    def get_record(
        self, entity_key: str, record_id: str, expansion_level: Optional[int] = None
    ) -> EntityWriteResponseV3:
        """v3 read by id; see :meth:`EntitiesServiceV3.get_record`."""
        spec = self._read_record_spec(entity_key, record_id, expansion_level)
        response = self.request(spec.method, spec.endpoint, params=spec.params)
        return EntityWriteResponseV3.model_validate(response.json())

    async def get_record_async(
        self, entity_key: str, record_id: str, expansion_level: Optional[int] = None
    ) -> EntityWriteResponseV3:
        """Async variant of :meth:`get_record`."""
        spec = self._read_record_spec(entity_key, record_id, expansion_level)
        response = await self.request_async(
            spec.method, spec.endpoint, params=spec.params
        )
        return EntityWriteResponseV3.model_validate(response.json())

    def update_record(
        self,
        entity_key: str,
        record_id: str,
        data: Any,
        expansion_level: Optional[int] = None,
    ) -> EntityWriteResponseV3:
        """v3 single update; see :meth:`EntitiesServiceV3.update_record`."""
        spec = self._write_spec(
            f"{entity_key}/update/{record_id}", data, expansion_level
        )
        response = self.request(
            spec.method, spec.endpoint, params=spec.params, json=spec.json
        )
        return EntityWriteResponseV3.model_validate(response.json())

    async def update_record_async(
        self,
        entity_key: str,
        record_id: str,
        data: Any,
        expansion_level: Optional[int] = None,
    ) -> EntityWriteResponseV3:
        """Async variant of :meth:`update_record`."""
        spec = self._write_spec(
            f"{entity_key}/update/{record_id}", data, expansion_level
        )
        response = await self.request_async(
            spec.method, spec.endpoint, params=spec.params, json=spec.json
        )
        return EntityWriteResponseV3.model_validate(response.json())

    def delete_record(self, entity_key: str, record_id: str) -> EntityWriteResponseV3:
        """v3 single delete; see :meth:`EntitiesServiceV3.delete_record`."""
        endpoint = Endpoint(f"{_V3_BASE}/{entity_key}/delete/{record_id}")
        response = self.request("DELETE", endpoint)
        return EntityWriteResponseV3.model_validate(response.json())

    async def delete_record_async(
        self, entity_key: str, record_id: str
    ) -> EntityWriteResponseV3:
        """Async variant of :meth:`delete_record`."""
        endpoint = Endpoint(f"{_V3_BASE}/{entity_key}/delete/{record_id}")
        response = await self.request_async("DELETE", endpoint)
        return EntityWriteResponseV3.model_validate(response.json())

    # ------------------------------------------------------------------
    # Batch record operations
    # ------------------------------------------------------------------

    def insert_records(
        self,
        entity_key: str,
        records: List[Any],
        expansion_level: Optional[int] = None,
        fail_on_first: Optional[bool] = None,
    ) -> BatchOperationResponse:
        """v3 batch insert; see :meth:`EntitiesServiceV3.insert_records`."""
        spec = self._batch_spec(
            f"{entity_key}/insert-batch", records, expansion_level, fail_on_first
        )
        response = self.request(
            spec.method, spec.endpoint, params=spec.params, json=spec.json
        )
        return BatchOperationResponse.model_validate(response.json())

    async def insert_records_async(
        self,
        entity_key: str,
        records: List[Any],
        expansion_level: Optional[int] = None,
        fail_on_first: Optional[bool] = None,
    ) -> BatchOperationResponse:
        """Async variant of :meth:`insert_records`."""
        spec = self._batch_spec(
            f"{entity_key}/insert-batch", records, expansion_level, fail_on_first
        )
        response = await self.request_async(
            spec.method, spec.endpoint, params=spec.params, json=spec.json
        )
        return BatchOperationResponse.model_validate(response.json())

    def update_records(
        self,
        entity_key: str,
        records: List[Any],
        expansion_level: Optional[int] = None,
        fail_on_first: Optional[bool] = None,
    ) -> BatchOperationResponse:
        """v3 batch update; see :meth:`EntitiesServiceV3.update_records`."""
        spec = self._batch_spec(
            f"{entity_key}/update-batch", records, expansion_level, fail_on_first
        )
        response = self.request(
            spec.method, spec.endpoint, params=spec.params, json=spec.json
        )
        return BatchOperationResponse.model_validate(response.json())

    async def update_records_async(
        self,
        entity_key: str,
        records: List[Any],
        expansion_level: Optional[int] = None,
        fail_on_first: Optional[bool] = None,
    ) -> BatchOperationResponse:
        """Async variant of :meth:`update_records`."""
        spec = self._batch_spec(
            f"{entity_key}/update-batch", records, expansion_level, fail_on_first
        )
        response = await self.request_async(
            spec.method, spec.endpoint, params=spec.params, json=spec.json
        )
        return BatchOperationResponse.model_validate(response.json())

    def delete_records(
        self,
        entity_key: str,
        record_ids: List[str],
        fail_on_first: Optional[bool] = None,
    ) -> BatchOperationResponse:
        """v3 batch delete; see :meth:`EntitiesServiceV3.delete_records`."""
        spec = self._delete_batch_spec(entity_key, record_ids, fail_on_first)
        response = self.request(
            spec.method, spec.endpoint, params=spec.params, json=spec.json
        )
        return BatchOperationResponse.model_validate(response.json())

    async def delete_records_async(
        self,
        entity_key: str,
        record_ids: List[str],
        fail_on_first: Optional[bool] = None,
    ) -> BatchOperationResponse:
        """Async variant of :meth:`delete_records`."""
        spec = self._delete_batch_spec(entity_key, record_ids, fail_on_first)
        response = await self.request_async(
            spec.method, spec.endpoint, params=spec.params, json=spec.json
        )
        return BatchOperationResponse.model_validate(response.json())

    # ------------------------------------------------------------------
    # Structured query
    # ------------------------------------------------------------------

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
        """v3 structured query; see :meth:`EntitiesServiceV3.retrieve_records`."""
        spec = self._query_spec(
            entity_key,
            filter_group,
            sort_options,
            selected_fields,
            expansions,
            expansion_level,
            aggregates,
            group_by,
            joins,
            binnings,
            start,
            limit,
            child_limit,
        )
        response = self.request(
            spec.method, spec.endpoint, params=spec.params, json=spec.json
        )
        return QueryResponseV3.model_validate(response.json() or {})

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
        spec = self._query_spec(
            entity_key,
            filter_group,
            sort_options,
            selected_fields,
            expansions,
            expansion_level,
            aggregates,
            group_by,
            joins,
            binnings,
            start,
            limit,
            child_limit,
        )
        response = await self.request_async(
            spec.method, spec.endpoint, params=spec.params, json=spec.json
        )
        return QueryResponseV3.model_validate(response.json() or {})

    # ------------------------------------------------------------------
    # Attachments
    # ------------------------------------------------------------------

    def upload_attachment(
        self,
        entity_id: str,
        record_id: str,
        field_name: str,
        file: Optional[FileContent] = None,
        file_path: Optional[str] = None,
        expansion_level: Optional[int] = None,
    ) -> Dict[str, Any]:
        """v3 attachment upload; see :meth:`EntitiesServiceV3.upload_attachment`."""
        spec = self._attachment_spec(entity_id, record_id, field_name, expansion_level)
        with EntityDataService._open_file(file, file_path) as handle:
            response = self.request(
                "POST", spec.endpoint, params=spec.params, files={"file": handle}
            )
        return response.json() if response.content else {}

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
        spec = self._attachment_spec(entity_id, record_id, field_name, expansion_level)
        with EntityDataService._open_file(file, file_path) as handle:
            response = await self.request_async(
                "POST", spec.endpoint, params=spec.params, files={"file": handle}
            )
        return response.json() if response.content else {}

    def download_attachment(
        self, entity_id: str, record_id: str, field_name: str
    ) -> bytes:
        """v3 attachment download; see :meth:`EntitiesServiceV3.download_attachment`."""
        spec = self._attachment_spec(entity_id, record_id, field_name)
        response = self.request("GET", spec.endpoint)
        return response.content

    async def download_attachment_async(
        self, entity_id: str, record_id: str, field_name: str
    ) -> bytes:
        """Async variant of :meth:`download_attachment`."""
        spec = self._attachment_spec(entity_id, record_id, field_name)
        response = await self.request_async("GET", spec.endpoint)
        return response.content

    def delete_attachment(
        self,
        entity_id: str,
        record_id: str,
        field_name: str,
        expansion_level: Optional[int] = None,
    ) -> Dict[str, Any]:
        """v3 attachment delete; see :meth:`EntitiesServiceV3.delete_attachment`."""
        spec = self._attachment_spec(entity_id, record_id, field_name, expansion_level)
        response = self.request("DELETE", spec.endpoint, params=spec.params)
        return response.json() if response.content else {}

    async def delete_attachment_async(
        self,
        entity_id: str,
        record_id: str,
        field_name: str,
        expansion_level: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Async variant of :meth:`delete_attachment`."""
        spec = self._attachment_spec(entity_id, record_id, field_name, expansion_level)
        response = await self.request_async("DELETE", spec.endpoint, params=spec.params)
        return response.json() if response.content else {}

    # ------------------------------------------------------------------
    # Request-spec builders
    # ------------------------------------------------------------------

    @staticmethod
    def _choiceset_values_spec(
        choiceset_id: str,
        start: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> RequestSpec:
        return RequestSpec(
            method="POST",
            endpoint=Endpoint(f"{_V3_BASE}/entity/{choiceset_id}/query_expansion"),
            json=build_query_body(start=start, limit=limit),
        )

    @staticmethod
    def _read_spec(
        entity_key: str,
        start: int,
        limit: int,
        expansion_level: Optional[int],
    ) -> RequestSpec:
        params: Dict[str, Any] = {"start": start, "limit": limit}
        if expansion_level is not None:
            params["expansionLevel"] = expansion_level
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(f"{_V3_BASE}/{entity_key}/read"),
            params=params,
        )

    @staticmethod
    def _read_record_spec(
        entity_key: str, record_id: str, expansion_level: Optional[int]
    ) -> RequestSpec:
        params: Dict[str, Any] = {}
        if expansion_level is not None:
            params["expansionLevel"] = expansion_level
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(f"{_V3_BASE}/{entity_key}/read/{record_id}"),
            params=params,
        )

    @staticmethod
    def _write_spec(
        path: str, data: Any, expansion_level: Optional[int]
    ) -> RequestSpec:
        params: Dict[str, Any] = {}
        if expansion_level is not None:
            params["expansionLevel"] = expansion_level
        return RequestSpec(
            method="POST",
            endpoint=Endpoint(f"{_V3_BASE}/{path}"),
            params=params,
            json=EntityDataService._record_to_dict(data),
        )

    @staticmethod
    def _batch_spec(
        path: str,
        records: List[Any],
        expansion_level: Optional[int],
        fail_on_first: Optional[bool],
    ) -> RequestSpec:
        return RequestSpec(
            method="POST",
            endpoint=Endpoint(f"{_V3_BASE}/{path}"),
            params=EntityDataService._batch_params(
                expansion_level=expansion_level, fail_on_first=fail_on_first
            ),
            json=[EntityDataService._record_to_dict(record) for record in records],
        )

    @staticmethod
    def _delete_batch_spec(
        entity_key: str, record_ids: List[str], fail_on_first: Optional[bool]
    ) -> RequestSpec:
        return RequestSpec(
            method="POST",
            endpoint=Endpoint(f"{_V3_BASE}/{entity_key}/delete-batch"),
            params=EntityDataService._batch_params(fail_on_first=fail_on_first),
            json=list(record_ids),
        )

    @staticmethod
    def _query_spec(
        entity_key: str,
        filter_group: Optional[EntityQueryFilterGroup],
        sort_options: Optional[List[EntityQuerySortOption]],
        selected_fields: Optional[List[str]],
        expansions: Optional[List[Any]],
        expansion_level: Optional[int],
        aggregates: Optional[List[EntityAggregate]],
        group_by: Optional[List[str]],
        joins: Optional[List[EntityJoin]],
        binnings: Optional[List[EntityBinning]],
        start: Optional[int],
        limit: Optional[int],
        child_limit: Optional[int],
    ) -> RequestSpec:
        params: Dict[str, Any] = {}
        if expansion_level is not None:
            params["expansionLevel"] = expansion_level
        return RequestSpec(
            method="POST",
            endpoint=Endpoint(f"{_V3_BASE}/{entity_key}/query"),
            params=params,
            json=build_query_body(
                filter_group=filter_group,
                sort_options=sort_options,
                selected_fields=selected_fields,
                expansions=expansions,
                aggregates=aggregates,
                group_by=group_by,
                joins=joins,
                binnings=binnings,
                start=start,
                limit=limit,
                child_limit=child_limit,
            ),
        )

    @staticmethod
    def _attachment_spec(
        entity_id: str,
        record_id: str,
        field_name: str,
        expansion_level: Optional[int] = None,
    ) -> RequestSpec:
        params: Dict[str, Any] = {}
        if expansion_level is not None:
            params["expansionLevel"] = expansion_level
        return RequestSpec(
            method="POST",
            endpoint=Endpoint(
                f"{_V3_BASE}/{entity_id}/records/{record_id}/attachments/{field_name}"
            ),
            params=params,
        )

    def _query_entities_for_records(self, sql_query: str) -> Any:
        """Federated SQL is version-agnostic; delegated by the facade to v1."""
        raise NotImplementedError  # pragma: no cover - not routed here
