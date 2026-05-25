"""Data-side operations for the Data Fabric entities surface.

Handles record CRUD (single and batch), structured queries, attachments,
choice-set value lookup, bulk import, and federated SQL queries. Schema
definitions are managed by :class:`EntitySchemaService` and exposed alongside
data operations through :class:`EntitiesService`.
"""

import json as json_module
import logging
from contextlib import nullcontext
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

import sqlparse
from httpx import HTTPStatusError, Response
from pydantic import BaseModel
from sqlparse.sql import Function, Identifier, IdentifierList, Parenthesis, Where
from sqlparse.tokens import DML, Keyword, Whitespace, Wildcard

from ..common._base_service import BaseService
from ..common._config import UiPathApiConfig
from ..common._execution_context import UiPathExecutionContext
from ..common._models import Endpoint, RequestSpec
from ..errors._enriched_exception import EnrichedException
from ..orchestrator._folder_service import FolderService
from ._entity_resolution import RoutingStrategy, create_routing_strategy
from .entities import (
    AggregateRow,
    ChoiceSetValue,
    EntityAggregate,
    EntityBinning,
    EntityImportRecordsResponse,
    EntityJoin,
    EntityQueryFilterGroup,
    EntityQuerySortOption,
    EntityRecord,
    EntityRecordsBatchResponse,
    EntityRecordsListResponse,
    QueryRoutingOverrideContext,
    RetrieveEntityRecordsResponse,
)

logger = logging.getLogger(__name__)

FileContent = bytes | bytearray | memoryview
"""Acceptable raw bytes types for attachment and CSV uploads."""

_FORBIDDEN_DML = {"INSERT", "UPDATE", "DELETE", "MERGE", "REPLACE"}
_FORBIDDEN_DDL = {"DROP", "ALTER", "CREATE", "TRUNCATE"}
_DISALLOWED_KEYWORDS = [
    "WITH",
    "UNION",
    "INTERSECT",
    "EXCEPT",
    "OVER",
    "ROLLUP",
    "CUBE",
    "GROUPING",
    "PARTITION",
]
_AGGREGATE_FUNCTIONS = ("COUNT", "SUM", "AVG", "MIN", "MAX")


class EntityDataService(BaseService):
    """HTTP service for entity-record and attachment operations.

    Backend target: ``datafabric_/api/EntityService/...`` plus
    ``datafabric_/api/Attachment/...`` for file attachments, and
    ``datafabric_/api/v1/query/execute`` for federated SQL queries.

    !!! warning "Preview Feature"
        This service is currently experimental. Behavior and parameters are
        subject to change in future versions.
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
        """Initialise the data service.

        Either pass a pre-built ``routing_strategy`` (the facade does this so
        both services share one) or supply the inputs and let this service
        construct its own.
        """
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
        """Internal implementation; see :meth:`EntitiesService.get_choiceset_values`."""
        spec = self._get_choiceset_values_spec(choiceset_id, start=start, limit=limit)
        response = self.request(
            spec.method, spec.endpoint, params=spec.params, json=spec.json
        )
        return self._parse_choiceset_values(response)

    async def get_choiceset_values_async(
        self,
        choiceset_id: str,
        start: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[ChoiceSetValue]:
        """Async variant of :meth:`get_choiceset_values`."""
        spec = self._get_choiceset_values_spec(choiceset_id, start=start, limit=limit)
        response = await self.request_async(
            spec.method, spec.endpoint, params=spec.params, json=spec.json
        )
        return self._parse_choiceset_values(response)

    # ------------------------------------------------------------------
    # List records (multi-record read with OData filters)
    # ------------------------------------------------------------------

    def list_records(
        self,
        entity_key: str,
        schema: Optional[Type[Any]] = None,
        start: Optional[int] = None,
        limit: Optional[int] = None,
        expansion_level: Optional[int] = None,
        filter: Optional[str] = None,
        orderby: Optional[str] = None,
        select: Optional[List[str]] = None,
        expand: Optional[List[str]] = None,
    ) -> EntityRecordsListResponse:
        """Internal implementation; see :meth:`EntitiesService.list_records`."""
        spec = self._list_records_spec(
            entity_key,
            start=start,
            limit=limit,
            expansion_level=expansion_level,
            filter=filter,
            orderby=orderby,
            select=select,
            expand=expand,
        )
        response = self.request(spec.method, spec.endpoint, params=spec.params)
        return self._build_records_list_response(response, schema, start, limit)

    async def list_records_async(
        self,
        entity_key: str,
        schema: Optional[Type[Any]] = None,
        start: Optional[int] = None,
        limit: Optional[int] = None,
        expansion_level: Optional[int] = None,
        filter: Optional[str] = None,
        orderby: Optional[str] = None,
        select: Optional[List[str]] = None,
        expand: Optional[List[str]] = None,
    ) -> EntityRecordsListResponse:
        """Async variant of :meth:`list_records`."""
        spec = self._list_records_spec(
            entity_key,
            start=start,
            limit=limit,
            expansion_level=expansion_level,
            filter=filter,
            orderby=orderby,
            select=select,
            expand=expand,
        )
        response = await self.request_async(
            spec.method, spec.endpoint, params=spec.params
        )
        return self._build_records_list_response(response, schema, start, limit)

    # ------------------------------------------------------------------
    # Single-record operations (fire trigger events; batch versions don't)
    # ------------------------------------------------------------------

    def insert_record(
        self,
        entity_key: str,
        data: Any,
        expansion_level: Optional[int] = None,
    ) -> EntityRecord:
        """Internal implementation; see :meth:`EntitiesService.insert_record`."""
        spec = self._insert_record_spec(entity_key, data, expansion_level)
        response = self.request(
            spec.method, spec.endpoint, params=spec.params, json=spec.json
        )
        return EntityRecord.model_validate(response.json())

    async def insert_record_async(
        self,
        entity_key: str,
        data: Any,
        expansion_level: Optional[int] = None,
    ) -> EntityRecord:
        """Async variant of :meth:`insert_record`."""
        spec = self._insert_record_spec(entity_key, data, expansion_level)
        response = await self.request_async(
            spec.method, spec.endpoint, params=spec.params, json=spec.json
        )
        return EntityRecord.model_validate(response.json())

    def get_record(
        self,
        entity_key: str,
        record_id: str,
        expansion_level: Optional[int] = None,
    ) -> EntityRecord:
        """Fetch a single record by its id."""
        spec = self._get_record_spec(entity_key, record_id, expansion_level)
        response = self.request(spec.method, spec.endpoint, params=spec.params)
        return EntityRecord.model_validate(response.json())

    async def get_record_async(
        self,
        entity_key: str,
        record_id: str,
        expansion_level: Optional[int] = None,
    ) -> EntityRecord:
        """Async variant of :meth:`get_record`."""
        spec = self._get_record_spec(entity_key, record_id, expansion_level)
        response = await self.request_async(
            spec.method, spec.endpoint, params=spec.params
        )
        return EntityRecord.model_validate(response.json())

    def update_record(
        self,
        entity_key: str,
        record_id: str,
        data: Any,
        expansion_level: Optional[int] = None,
    ) -> EntityRecord:
        """Internal implementation; see :meth:`EntitiesService.update_record`."""
        spec = self._update_record_spec(entity_key, record_id, data, expansion_level)
        response = self.request(
            spec.method, spec.endpoint, params=spec.params, json=spec.json
        )
        return EntityRecord.model_validate(response.json())

    async def update_record_async(
        self,
        entity_key: str,
        record_id: str,
        data: Any,
        expansion_level: Optional[int] = None,
    ) -> EntityRecord:
        """Async variant of :meth:`update_record`."""
        spec = self._update_record_spec(entity_key, record_id, data, expansion_level)
        response = await self.request_async(
            spec.method, spec.endpoint, params=spec.params, json=spec.json
        )
        return EntityRecord.model_validate(response.json())

    def delete_record(self, entity_key: str, record_id: str) -> None:
        """Delete a single record by id."""
        spec = self._delete_record_spec(entity_key, record_id)
        self.request(spec.method, spec.endpoint)

    async def delete_record_async(self, entity_key: str, record_id: str) -> None:
        """Async variant of :meth:`delete_record`."""
        spec = self._delete_record_spec(entity_key, record_id)
        await self.request_async(spec.method, spec.endpoint)

    # ------------------------------------------------------------------
    # Batch record operations
    # ------------------------------------------------------------------

    def insert_records(
        self,
        entity_key: str,
        records: List[Any],
        schema: Optional[Type[Any]] = None,
        expansion_level: Optional[int] = None,
        fail_on_first: Optional[bool] = None,
    ) -> EntityRecordsBatchResponse:
        """Internal implementation; see :meth:`EntitiesService.insert_records`."""
        spec = self._insert_batch_spec(
            entity_key,
            records,
            expansion_level=expansion_level,
            fail_on_first=fail_on_first,
        )
        response = self._request_or_extract_batch(
            sync_call=lambda: self.request(
                spec.method, spec.endpoint, params=spec.params, json=spec.json
            )
        )
        if isinstance(response, EntityRecordsBatchResponse):
            return response
        return self.validate_entity_batch(response, schema)

    async def insert_records_async(
        self,
        entity_key: str,
        records: List[Any],
        schema: Optional[Type[Any]] = None,
        expansion_level: Optional[int] = None,
        fail_on_first: Optional[bool] = None,
    ) -> EntityRecordsBatchResponse:
        """Async variant of :meth:`insert_records`."""
        spec = self._insert_batch_spec(
            entity_key,
            records,
            expansion_level=expansion_level,
            fail_on_first=fail_on_first,
        )

        async def _send_batch() -> Response:
            return await self.request_async(
                spec.method, spec.endpoint, params=spec.params, json=spec.json
            )

        result = await self._request_or_extract_batch_async(_send_batch)
        if isinstance(result, EntityRecordsBatchResponse):
            return result
        return self.validate_entity_batch(result, schema)

    def update_records(
        self,
        entity_key: str,
        records: List[Any],
        schema: Optional[Type[Any]] = None,
        expansion_level: Optional[int] = None,
        fail_on_first: Optional[bool] = None,
    ) -> EntityRecordsBatchResponse:
        """Internal implementation; see :meth:`EntitiesService.update_records`."""
        normalized = [self._record_to_dict(record) for record in records]
        if schema is not None:
            for record in normalized:
                EntityRecord.from_data(data=record, model=schema)

        spec = self._update_batch_spec(
            entity_key,
            normalized,
            expansion_level=expansion_level,
            fail_on_first=fail_on_first,
        )
        response = self._request_or_extract_batch(
            sync_call=lambda: self.request(
                spec.method, spec.endpoint, params=spec.params, json=spec.json
            )
        )
        if isinstance(response, EntityRecordsBatchResponse):
            return response
        return self.validate_entity_batch(response, schema)

    async def update_records_async(
        self,
        entity_key: str,
        records: List[Any],
        schema: Optional[Type[Any]] = None,
        expansion_level: Optional[int] = None,
        fail_on_first: Optional[bool] = None,
    ) -> EntityRecordsBatchResponse:
        """Async variant of :meth:`update_records`."""
        normalized = [self._record_to_dict(record) for record in records]
        if schema is not None:
            for record in normalized:
                EntityRecord.from_data(data=record, model=schema)

        spec = self._update_batch_spec(
            entity_key,
            normalized,
            expansion_level=expansion_level,
            fail_on_first=fail_on_first,
        )

        async def _send_batch() -> Response:
            return await self.request_async(
                spec.method, spec.endpoint, params=spec.params, json=spec.json
            )

        result = await self._request_or_extract_batch_async(_send_batch)
        if isinstance(result, EntityRecordsBatchResponse):
            return result
        return self.validate_entity_batch(result, schema)

    def delete_records(
        self,
        entity_key: str,
        record_ids: List[str],
        fail_on_first: Optional[bool] = None,
    ) -> EntityRecordsBatchResponse:
        """Delete multiple records by id in a single batch."""
        spec = self._delete_batch_spec(
            entity_key, record_ids, fail_on_first=fail_on_first
        )
        result = self._request_or_extract_batch(
            sync_call=lambda: self.request(
                spec.method, spec.endpoint, params=spec.params, json=spec.json
            )
        )
        if isinstance(result, EntityRecordsBatchResponse):
            return result
        return EntityRecordsBatchResponse.model_validate(result.json())

    async def delete_records_async(
        self,
        entity_key: str,
        record_ids: List[str],
        fail_on_first: Optional[bool] = None,
    ) -> EntityRecordsBatchResponse:
        """Async variant of :meth:`delete_records`."""
        spec = self._delete_batch_spec(
            entity_key, record_ids, fail_on_first=fail_on_first
        )

        async def _send_batch() -> Response:
            return await self.request_async(
                spec.method, spec.endpoint, params=spec.params, json=spec.json
            )

        result = await self._request_or_extract_batch_async(_send_batch)
        if isinstance(result, EntityRecordsBatchResponse):
            return result
        return EntityRecordsBatchResponse.model_validate(result.json())

    # ------------------------------------------------------------------
    # Structured query (POST /entity/{id}/query)
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
    ) -> RetrieveEntityRecordsResponse:
        """Internal implementation; see :meth:`EntitiesService.retrieve_records`."""
        spec = self._retrieve_records_spec(
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
        )
        response = self.request(
            spec.method, spec.endpoint, params=spec.params, json=spec.json
        )
        return self._parse_query_response(response, start=start, limit=limit)

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
    ) -> RetrieveEntityRecordsResponse:
        """Async variant of :meth:`retrieve_records`."""
        spec = self._retrieve_records_spec(
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
        )
        response = await self.request_async(
            spec.method, spec.endpoint, params=spec.params, json=spec.json
        )
        return self._parse_query_response(response, start=start, limit=limit)

    # ------------------------------------------------------------------
    # Federated SQL query
    # ------------------------------------------------------------------

    def query_entity_records(
        self,
        sql_query: str,
    ) -> List[Dict[str, Any]]:
        """Internal implementation; see :meth:`EntitiesService.query_entity_records`."""
        return self._query_entities_for_records(sql_query)

    async def query_entity_records_async(
        self,
        sql_query: str,
    ) -> List[Dict[str, Any]]:
        """Async variant of :meth:`query_entity_records`."""
        return await self._query_entities_for_records_async(sql_query)

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
        """Internal implementation; see :meth:`EntitiesService.upload_attachment`."""
        spec = self._attachment_endpoint(
            entity_id, record_id, field_name, expansion_level
        )
        with self._open_file(file, file_path) as handle:
            response = self.request(
                "POST",
                spec.endpoint,
                params=spec.params,
                files={"file": handle},
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
        spec = self._attachment_endpoint(
            entity_id, record_id, field_name, expansion_level
        )
        with self._open_file(file, file_path) as handle:
            response = await self.request_async(
                "POST",
                spec.endpoint,
                params=spec.params,
                files={"file": handle},
            )
        return response.json() if response.content else {}

    def download_attachment(
        self, entity_id: str, record_id: str, field_name: str
    ) -> bytes:
        """Internal implementation; see :meth:`EntitiesService.download_attachment`."""
        spec = self._attachment_endpoint(entity_id, record_id, field_name)
        response = self.request("GET", spec.endpoint)
        return response.content

    async def download_attachment_async(
        self, entity_id: str, record_id: str, field_name: str
    ) -> bytes:
        """Async variant of :meth:`download_attachment`."""
        spec = self._attachment_endpoint(entity_id, record_id, field_name)
        response = await self.request_async("GET", spec.endpoint)
        return response.content

    def delete_attachment(
        self,
        entity_id: str,
        record_id: str,
        field_name: str,
        expansion_level: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Internal implementation; see :meth:`EntitiesService.delete_attachment`."""
        spec = self._attachment_endpoint(
            entity_id, record_id, field_name, expansion_level
        )
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
        spec = self._attachment_endpoint(
            entity_id, record_id, field_name, expansion_level
        )
        response = await self.request_async("DELETE", spec.endpoint, params=spec.params)
        return response.json() if response.content else {}

    # ------------------------------------------------------------------
    # Bulk import
    # ------------------------------------------------------------------

    def import_records(
        self,
        entity_id: str,
        file: Optional[FileContent] = None,
        file_path: Optional[str] = None,
    ) -> EntityImportRecordsResponse:
        """Internal implementation; see :meth:`EntitiesService.import_records`."""
        spec = self._import_records_spec(entity_id)
        with self._open_file(file, file_path) as handle:
            response = self.request(spec.method, spec.endpoint, files={"file": handle})
        return EntityImportRecordsResponse.model_validate(response.json() or {})

    async def import_records_async(
        self,
        entity_id: str,
        file: Optional[FileContent] = None,
        file_path: Optional[str] = None,
    ) -> EntityImportRecordsResponse:
        """Async variant of :meth:`import_records`."""
        spec = self._import_records_spec(entity_id)
        with self._open_file(file, file_path) as handle:
            response = await self.request_async(
                spec.method, spec.endpoint, files={"file": handle}
            )
        return EntityImportRecordsResponse.model_validate(response.json() or {})

    # ------------------------------------------------------------------
    # Public helper for batch response validation
    # ------------------------------------------------------------------

    def validate_entity_batch(
        self,
        batch_response: Response,
        schema: Optional[Type[Any]] = None,
    ) -> EntityRecordsBatchResponse:
        """Internal implementation; see :meth:`EntitiesService.validate_entity_batch`."""
        parsed = EntityRecordsBatchResponse.model_validate(batch_response.json())

        validated_successful_records = []
        for successful_record in parsed.success_records:
            data = successful_record.model_dump(by_alias=True)
            if data.get("Id") is not None:
                validated_successful_records.append(
                    EntityRecord.from_data(data=data, model=schema)
                )

        return EntityRecordsBatchResponse(
            success_records=validated_successful_records,
            failure_records=parsed.failure_records,
        )

    # ------------------------------------------------------------------
    # Internal helpers — request specs
    # ------------------------------------------------------------------

    def _query_entities_for_records(self, sql_query: str) -> List[Dict[str, Any]]:
        """Synchronously run a validated SQL query through the federated query engine."""
        self._validate_sql_query(sql_query)
        routing_context = self._routing_strategy.resolve()
        spec = self._query_entity_records_spec(sql_query, routing_context)
        response = self.request(spec.method, spec.endpoint, json=spec.json)
        return response.json().get("results", [])

    async def _query_entities_for_records_async(
        self, sql_query: str
    ) -> List[Dict[str, Any]]:
        """Asynchronously run a validated SQL query through the federated query engine."""
        self._validate_sql_query(sql_query)
        routing_context = await self._routing_strategy.resolve_async()
        spec = self._query_entity_records_spec(sql_query, routing_context)
        response = await self.request_async(spec.method, spec.endpoint, json=spec.json)
        return response.json().get("results", [])

    @staticmethod
    def _list_records_spec(
        entity_key: str,
        start: Optional[int] = None,
        limit: Optional[int] = None,
        expansion_level: Optional[int] = None,
        filter: Optional[str] = None,
        orderby: Optional[str] = None,
        select: Optional[List[str]] = None,
        expand: Optional[List[str]] = None,
    ) -> RequestSpec:
        """Build the GET spec for the multi-record read endpoint."""
        params: Dict[str, Any] = {}
        if start is not None:
            params["start"] = start
        if limit is not None:
            params["limit"] = limit
        if expansion_level is not None:
            params["expansionLevel"] = expansion_level
        if filter is not None:
            params["$filter"] = filter
        if orderby is not None:
            params["$orderby"] = orderby
        if select:
            params["$select"] = ",".join(select)
        if expand:
            params["$expand"] = ",".join(expand)
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(
                f"datafabric_/api/EntityService/entity/{entity_key}/read"
            ),
            params=params,
        )

    @staticmethod
    def _insert_record_spec(
        entity_key: str,
        data: Any,
        expansion_level: Optional[int] = None,
    ) -> RequestSpec:
        """Build the POST spec for inserting a single record."""
        params: Dict[str, Any] = {}
        if expansion_level is not None:
            params["expansionLevel"] = expansion_level
        return RequestSpec(
            method="POST",
            endpoint=Endpoint(
                f"datafabric_/api/EntityService/entity/{entity_key}/insert"
            ),
            params=params,
            json=EntityDataService._record_to_dict(data),
        )

    @staticmethod
    def _get_record_spec(
        entity_key: str,
        record_id: str,
        expansion_level: Optional[int] = None,
    ) -> RequestSpec:
        """Build the GET spec for fetching a single record by id."""
        params: Dict[str, Any] = {}
        if expansion_level is not None:
            params["expansionLevel"] = expansion_level
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(
                f"datafabric_/api/EntityService/entity/{entity_key}/read/{record_id}"
            ),
            params=params,
        )

    @staticmethod
    def _update_record_spec(
        entity_key: str,
        record_id: str,
        data: Any,
        expansion_level: Optional[int] = None,
    ) -> RequestSpec:
        """Build the POST spec for updating a single record by id."""
        params: Dict[str, Any] = {}
        if expansion_level is not None:
            params["expansionLevel"] = expansion_level
        return RequestSpec(
            method="POST",
            endpoint=Endpoint(
                f"datafabric_/api/EntityService/entity/{entity_key}/update/{record_id}"
            ),
            params=params,
            json=EntityDataService._record_to_dict(data),
        )

    @staticmethod
    def _delete_record_spec(entity_key: str, record_id: str) -> RequestSpec:
        """Build the DELETE spec for removing a single record by id."""
        return RequestSpec(
            method="DELETE",
            endpoint=Endpoint(
                f"datafabric_/api/EntityService/entity/{entity_key}/delete/{record_id}"
            ),
        )

    @staticmethod
    def _insert_batch_spec(
        entity_key: str,
        records: List[Any],
        expansion_level: Optional[int] = None,
        fail_on_first: Optional[bool] = None,
    ) -> RequestSpec:
        """Build the POST spec for the batch-insert endpoint."""
        params = EntityDataService._batch_params(
            expansion_level=expansion_level, fail_on_first=fail_on_first
        )
        return RequestSpec(
            method="POST",
            endpoint=Endpoint(
                f"datafabric_/api/EntityService/entity/{entity_key}/insert-batch"
            ),
            params=params,
            json=[EntityDataService._record_to_dict(record) for record in records],
        )

    @staticmethod
    def _update_batch_spec(
        entity_key: str,
        records: List[Dict[str, Any]],
        expansion_level: Optional[int] = None,
        fail_on_first: Optional[bool] = None,
    ) -> RequestSpec:
        """Build the POST spec for the batch-update endpoint."""
        params = EntityDataService._batch_params(
            expansion_level=expansion_level, fail_on_first=fail_on_first
        )
        return RequestSpec(
            method="POST",
            endpoint=Endpoint(
                f"datafabric_/api/EntityService/entity/{entity_key}/update-batch"
            ),
            params=params,
            json=records,
        )

    @staticmethod
    def _delete_batch_spec(
        entity_key: str,
        record_ids: List[str],
        fail_on_first: Optional[bool] = None,
    ) -> RequestSpec:
        """Build the POST spec for the batch-delete endpoint."""
        params = EntityDataService._batch_params(fail_on_first=fail_on_first)
        return RequestSpec(
            method="POST",
            endpoint=Endpoint(
                f"datafabric_/api/EntityService/entity/{entity_key}/delete-batch"
            ),
            params=params,
            json=record_ids,
        )

    @staticmethod
    def _batch_params(
        expansion_level: Optional[int] = None,
        fail_on_first: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Build the optional URL params common to all batch endpoints."""
        params: Dict[str, Any] = {}
        if expansion_level is not None:
            params["expansionLevel"] = expansion_level
        if fail_on_first is not None:
            params["failOnFirst"] = "true" if fail_on_first else "false"
        return params

    @staticmethod
    def _retrieve_records_spec(
        entity_key: str,
        filter_group: Optional[EntityQueryFilterGroup] = None,
        sort_options: Optional[List[EntityQuerySortOption]] = None,
        selected_fields: Optional[List[str]] = None,
        expansions: Optional[List[Any]] = None,
        expansion_level: Optional[int] = None,
        aggregates: Optional[List[Any]] = None,
        group_by: Optional[List[str]] = None,
        joins: Optional[List[EntityJoin]] = None,
        binnings: Optional[List[EntityBinning]] = None,
        start: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> RequestSpec:
        """Build the request spec for the structured-query endpoint.

        Filters, sorting, projection, expansions, aggregates, group-by, joins,
        binnings, ``start``, and ``limit`` are placed in the JSON body;
        ``expansionLevel`` is a URL query parameter. The V2 endpoint is used
        only when ``binnings`` are supplied.
        """
        body: Dict[str, Any] = {}
        if filter_group is not None:
            body["filterGroup"] = filter_group.model_dump(
                by_alias=True, exclude_none=True
            )
        if sort_options:
            body["sortOptions"] = [
                opt.model_dump(by_alias=True, exclude_none=True) for opt in sort_options
            ]
        if selected_fields:
            body["selectedFields"] = list(selected_fields)
        if expansions:
            body["expansions"] = [
                e.model_dump(by_alias=True, exclude_none=True)
                if isinstance(e, BaseModel)
                else e
                for e in expansions
            ]
        if aggregates:
            body["aggregates"] = [
                a.model_dump(by_alias=True, exclude_none=True)
                if isinstance(a, BaseModel)
                else a
                for a in aggregates
            ]
        if group_by:
            body["groupBy"] = list(group_by)
        if joins:
            body["joins"] = [
                j.model_dump(by_alias=True, exclude_none=True) for j in joins
            ]
        if binnings:
            body["binnings"] = [
                b.model_dump(by_alias=True, exclude_none=True) for b in binnings
            ]
        if start is not None:
            body["start"] = start
        if limit is not None:
            body["limit"] = limit

        params: Dict[str, Any] = {}
        if expansion_level is not None:
            params["expansionLevel"] = expansion_level

        if binnings:
            endpoint = Endpoint(
                f"datafabric_/api/v2/EntityService/entity/{entity_key}/query"
            )
        else:
            endpoint = Endpoint(
                f"datafabric_/api/EntityService/entity/{entity_key}/query"
            )

        return RequestSpec(
            method="POST",
            endpoint=endpoint,
            params=params,
            json=body,
        )

    @staticmethod
    def _query_entity_records_spec(
        sql_query: str,
        routing_context: Optional[QueryRoutingOverrideContext] = None,
    ) -> RequestSpec:
        """Build the POST spec for the federated SQL query endpoint."""
        body: Dict[str, Any] = {"query": sql_query}
        if routing_context:
            body["routingContext"] = routing_context.model_dump(
                by_alias=True, exclude_none=True
            )
        return RequestSpec(
            method="POST",
            endpoint=Endpoint("datafabric_/api/v1/query/execute"),
            json=body,
        )

    @staticmethod
    def _get_choiceset_values_spec(
        choiceset_id: str,
        start: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> RequestSpec:
        """Build the POST spec for the choice-set values endpoint."""
        params: Dict[str, Any] = {}
        if start is not None:
            params["start"] = start
        if limit is not None:
            params["limit"] = limit
        return RequestSpec(
            method="POST",
            endpoint=Endpoint(
                f"datafabric_/api/EntityService/entity/{choiceset_id}/query_expansion"
            ),
            params=params,
            json={},
        )

    @staticmethod
    def _attachment_endpoint(
        entity_id: str,
        record_id: str,
        field_name: str,
        expansion_level: Optional[int] = None,
    ) -> RequestSpec:
        """Return the attachment endpoint plus any ``expansionLevel`` query param.

        The HTTP verb is supplied by the caller; only the URL and query
        parameters depend on these arguments.
        """
        params: Dict[str, Any] = {}
        if expansion_level is not None:
            params["expansionLevel"] = expansion_level
        return RequestSpec(
            method="POST",
            endpoint=Endpoint(
                f"datafabric_/api/Attachment/entity/{entity_id}/{record_id}/{field_name}"
            ),
            params=params,
        )

    @staticmethod
    def _import_records_spec(entity_id: str) -> RequestSpec:
        """Build the POST spec for the bulk-upload (CSV import) endpoint."""
        return RequestSpec(
            method="POST",
            endpoint=Endpoint(
                f"datafabric_/api/EntityService/entity/{entity_id}/bulk-upload"
            ),
        )

    @staticmethod
    def _open_file(file: Optional[FileContent], file_path: Optional[str]) -> Any:
        """Yield a file-like object from raw bytes or a path on disk.

        Exactly one of ``file`` and ``file_path`` must be supplied.
        """
        if (file is None) == (file_path is None):
            raise ValueError(
                "Provide exactly one of `file` (bytes) or `file_path` (str path on disk)."
            )
        if file_path is not None:
            return open(Path(file_path), "rb")
        return nullcontext(file)

    # ------------------------------------------------------------------
    # Internal helpers — response parsing and record normalisation
    # ------------------------------------------------------------------

    @staticmethod
    def _record_to_dict(record: Any) -> Dict[str, Any]:
        """Normalize an input record to a plain dict.

        Accepts dicts, Pydantic ``BaseModel`` (including :class:`EntityRecord`),
        or any object exposing ``__dict__``. Explicit ``None`` values are
        preserved so callers can clear fields by setting them to ``None`` on a
        model instance — only unset fields (whose Pydantic default applies) are
        dropped via ``exclude_unset=True``.
        """
        if isinstance(record, dict):
            return dict(record)
        if isinstance(record, BaseModel):
            return record.model_dump(by_alias=True, exclude_unset=True)
        if hasattr(record, "__dict__"):
            return {k: v for k, v in record.__dict__.items() if not k.startswith("_")}
        raise TypeError(
            f"Cannot convert record of type {type(record).__name__} to dict — "
            "pass a dict, an EntityRecord, a Pydantic BaseModel, or an object with __dict__."
        )

    @staticmethod
    def _build_records_list_response(
        response: Response,
        schema: Optional[Type[Any]],
        start: Optional[int],
        limit: Optional[int],
    ) -> EntityRecordsListResponse:
        """Build an :class:`EntityRecordsListResponse` from a list-records body."""
        body = response.json() or {}
        records_data = body.get("value", [])
        total_count = int(
            body.get("totalRecordCount", body.get("totalCount", len(records_data))) or 0
        )
        records = [
            EntityRecord.from_data(data=record, model=schema) for record in records_data
        ]

        next_cursor = body.get("nextCursor")
        if limit is not None and limit > 0:
            consumed = (start or 0) + len(records)
            has_next_page = consumed < total_count
        else:
            has_next_page = bool(body.get("hasNextPage", False))

        return EntityRecordsListResponse(
            items=records,
            total_count=total_count,
            has_next_page=has_next_page,
            next_cursor=next_cursor,
        )

    @staticmethod
    def _parse_query_response(
        response: Response,
        start: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> RetrieveEntityRecordsResponse:
        """Parse a query response into :class:`RetrieveEntityRecordsResponse`.

        Rows that include an ``Id`` field are parsed as :class:`EntityRecord`;
        rows that don't (aggregate / group-by / binning results) are parsed as
        :class:`AggregateRow`. ``has_next_page`` is derived from
        ``start + len(items) < total_count`` whenever ``limit`` is supplied;
        ``next_cursor`` is populated only when the backend returns one,
        otherwise the caller paginates by passing the next ``start``.
        """
        body = response.json() or {}
        items_raw = body.get("value", []) or []
        items: List[EntityRecord | AggregateRow] = []
        for raw in items_raw:
            if isinstance(raw, dict) and isinstance(raw.get("Id"), str):
                items.append(EntityRecord.from_data(data=raw))
            else:
                items.append(AggregateRow.model_validate(raw))

        total_count = int(body.get("totalRecordCount", body.get("totalCount", 0)) or 0)

        next_cursor: Optional[str] = body.get("nextCursor")
        has_next_page = bool(body.get("hasNextPage", False))
        if next_cursor is None and limit is not None and limit > 0:
            consumed = (start or 0) + len(items)
            has_next_page = consumed < total_count

        return RetrieveEntityRecordsResponse(
            items=items,
            total_count=total_count,
            has_next_page=has_next_page,
            next_cursor=next_cursor,
        )

    @staticmethod
    def _parse_choiceset_values(response: Response) -> List[ChoiceSetValue]:
        """Decode and return the choice-set values from a query-expansion response."""
        data = response.json()
        raw_values = data.get("jsonValue", "[]")
        items = (
            json_module.loads(raw_values) if isinstance(raw_values, str) else raw_values
        )
        return [ChoiceSetValue.model_validate(item) for item in items]

    # ------------------------------------------------------------------
    # Internal helpers — batch error recovery
    # ------------------------------------------------------------------

    def _request_or_extract_batch(
        self,
        sync_call: Any,
    ) -> Response | EntityRecordsBatchResponse:
        """Run a batch request and recover per-record failures from a 400 body.

        On HTTP 400 with a body that lists both ``successRecords`` and
        ``failureRecords``, returns the parsed batch response instead of
        raising. All other errors propagate.
        """
        try:
            return sync_call()
        except EnrichedException as exc:
            extracted = self._extract_batch_response_from_error(exc)
            if extracted is not None:
                return extracted
            raise

    async def _request_or_extract_batch_async(
        self,
        async_call: Any,
    ) -> Response | EntityRecordsBatchResponse:
        """Async variant of :meth:`_request_or_extract_batch`."""
        try:
            return await async_call()
        except EnrichedException as exc:
            extracted = self._extract_batch_response_from_error(exc)
            if extracted is not None:
                return extracted
            raise

    @staticmethod
    def _extract_batch_response_from_error(
        exc: EnrichedException,
    ) -> Optional[EntityRecordsBatchResponse]:
        """Return a parsed batch response when the error body matches the per-record-failure shape.

        Recovery is intentionally narrow: only HTTP 400 with a JSON object
        containing list-typed ``successRecords`` and ``failureRecords`` keys.
        Returns ``None`` for any other status, body shape, or parse failure
        so that the original error propagates.
        """
        cause = exc.__cause__
        if not isinstance(cause, HTTPStatusError):
            return None
        if cause.response.status_code != 400:
            return None
        try:
            data = cause.response.json()
        except Exception:
            return None
        if not isinstance(data, dict):
            return None
        if not (
            isinstance(data.get("successRecords"), list)
            and isinstance(data.get("failureRecords"), list)
        ):
            return None
        try:
            return EntityRecordsBatchResponse.model_validate(data)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Internal helpers — SQL validation (federated query path)
    # ------------------------------------------------------------------

    def _validate_sql_query(self, sql_query: str) -> None:
        """Validate a SQL string for the federated query endpoint client-side."""
        query = sql_query.strip().rstrip(";").strip()
        if not query:
            raise ValueError("SQL query cannot be empty.")

        statements = sqlparse.parse(query)
        if len(statements) != 1 or not statements[0].tokens:
            raise ValueError("Only a single SELECT statement is allowed.")

        stmt = statements[0]
        stmt_type = stmt.get_type()

        if stmt_type != "SELECT":
            raise ValueError("Only SELECT statements are allowed.")

        keywords = set()
        for token in stmt.flatten():
            if token.ttype in Keyword:
                keywords.add(token.normalized)

        for kw in _FORBIDDEN_DML:
            if kw in keywords:
                raise ValueError(f"SQL keyword '{kw}' is not allowed.")

        for kw in _FORBIDDEN_DDL:
            if kw in keywords:
                raise ValueError(f"SQL keyword '{kw}' is not allowed.")

        for kw in _DISALLOWED_KEYWORDS:
            if kw in keywords:
                raise ValueError(
                    f"SQL construct '{kw}' is not allowed in entity queries."
                )

        if self._has_subquery(stmt):
            raise ValueError("Subqueries are not allowed.")

        has_where = any(isinstance(t, Where) for t in stmt.tokens)
        has_limit = "LIMIT" in keywords
        has_from = "FROM" in keywords

        if not has_from:
            raise ValueError("Queries must include a FROM clause.")

        projection = self._projection_tokens(stmt)

        if self._projection_has_count_star(projection):
            raise ValueError(
                "COUNT(*) is not supported. Use COUNT(column_name) instead."
            )

        has_aggregate = self._projection_has_aggregate(projection)

        if not has_where and not has_limit and not has_aggregate:
            raise ValueError("Queries without WHERE must include a LIMIT clause.")

        has_bare_wildcard = self._projection_has_bare_wildcard(projection)
        if has_bare_wildcard:
            raise ValueError("SELECT * is not allowed. Specify column names instead.")
        if not has_where and self._projection_column_count(projection) > 4:
            raise ValueError(
                "Selecting more than 4 columns without filtering is not allowed."
            )

    @staticmethod
    def _projection_has_aggregate(
        projection: List[sqlparse.sql.Token],
    ) -> bool:
        """Return ``True`` when the projection contains an aggregate function call."""

        def _has_agg(token: sqlparse.sql.Token) -> bool:
            if isinstance(token, Function):
                return token.get_name().upper() in _AGGREGATE_FUNCTIONS
            if isinstance(token, Identifier):
                return any(_has_agg(child) for child in token.tokens)
            return False

        for node in projection:
            if _has_agg(node):
                return True
            if isinstance(node, IdentifierList):
                if any(_has_agg(child) for child in node.tokens):
                    return True
        return False

    @staticmethod
    def _projection_has_count_star(
        projection: List[sqlparse.sql.Token],
    ) -> bool:
        """Return ``True`` when the projection contains ``COUNT(*)``."""

        def _is_count_star(func: Function) -> bool:
            if func.get_name().upper() != "COUNT":
                return False
            return any(t.ttype is Wildcard for t in func.flatten())

        def _has_count_star(token: sqlparse.sql.Token) -> bool:
            if isinstance(token, Function):
                return _is_count_star(token)
            if isinstance(token, Identifier):
                return any(_has_count_star(child) for child in token.tokens)
            return False

        for node in projection:
            if _has_count_star(node):
                return True
            if isinstance(node, IdentifierList):
                if any(_has_count_star(child) for child in node.tokens):
                    return True
        return False

    @staticmethod
    def _projection_has_bare_wildcard(
        projection: List[sqlparse.sql.Token],
    ) -> bool:
        """Return ``True`` for a bare ``*`` or qualified ``table.*`` outside a function."""

        def _identifier_has_wildcard(ident: Identifier) -> bool:
            return any(t.ttype is Wildcard for t in ident.tokens)

        for node in projection:
            if node.ttype is Wildcard:
                return True
            if isinstance(node, Identifier) and _identifier_has_wildcard(node):
                return True
            if isinstance(node, IdentifierList):
                for child in node.tokens:
                    if child.ttype is Wildcard:
                        return True
                    if isinstance(child, Identifier) and _identifier_has_wildcard(
                        child
                    ):
                        return True
        return False

    @staticmethod
    def _has_subquery(stmt: sqlparse.sql.Statement) -> bool:
        """Recursively walk the AST looking for a SELECT inside parentheses."""

        def _walk(token: sqlparse.sql.Token) -> bool:
            if isinstance(token, Parenthesis):
                for child in token.flatten():
                    if child.ttype is DML and child.normalized == "SELECT":
                        return True
            if hasattr(token, "tokens"):
                for child in token.tokens:
                    if _walk(child):
                        return True
            return False

        for token in stmt.tokens:
            if _walk(token):
                return True
        return False

    @staticmethod
    def _projection_tokens(
        stmt: sqlparse.sql.Statement,
    ) -> List[sqlparse.sql.Token]:
        """Return the non-flattened AST nodes between the first SELECT and FROM."""
        tokens: List[sqlparse.sql.Token] = []
        collecting = False
        for token in stmt.tokens:
            if token.ttype is DML and token.normalized == "SELECT":
                collecting = True
                continue
            if token.ttype is Keyword and token.normalized in ("FROM", "INTO"):
                break
            if token.ttype is Keyword and token.normalized == "DISTINCT":
                continue
            if collecting and token.ttype is not Whitespace:
                tokens.append(token)
        return tokens

    @staticmethod
    def _projection_column_count(
        projection: List[sqlparse.sql.Token],
    ) -> int:
        """Return the number of columns referenced by the projection."""
        for node in projection:
            if isinstance(node, IdentifierList):
                return len(list(node.get_identifiers()))
            if isinstance(node, (Identifier, Function)):
                return 1
            if node.ttype is Wildcard:
                return 1
        return 0
