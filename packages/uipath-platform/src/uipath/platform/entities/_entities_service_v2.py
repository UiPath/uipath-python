"""Public facade for the v2 Data Fabric entities API (preview).

The v2 backend is a **partial** surface: it re-implements only structured
``query`` and single-record ``read`` for records, plus entity listing. Its
response shapes are identical to v1, so :class:`EntitiesServiceV2` reuses the v1
models (:class:`RetrieveEntityRecordsResponse`, :class:`EntityRecord`,
:class:`Entity`) and parsing, overriding only the endpoints to target
``datafabric_/api/v2/...``.

Reach it via ``sdk.entities_v2``. Operations the v2 backend does not implement
(insert/update/delete, batch, attachments, schema writes, choice-set values)
are intentionally absent — use ``sdk.entities`` (v1) or ``sdk.entities_v3`` for
those.
"""

import logging
from typing import Any, List, Optional

from uipath.core.tracing import traced

from ..common._base_service import BaseService
from ..common._config import UiPathApiConfig
from ..common._execution_context import UiPathExecutionContext
from ..common._models import Endpoint, RequestSpec
from ..orchestrator._folder_service import FolderService
from ._entity_data_service import EntityDataService, build_query_body
from ._entity_resolution import create_routing_strategy
from ._entity_schema_service import EntitySchemaService
from .entities import (
    Entity,
    EntityAggregate,
    EntityBinning,
    EntityJoin,
    EntityQueryFilterGroup,
    EntityQuerySortOption,
    EntityRecord,
    QueryRoutingOverrideContext,
    RetrieveEntityRecordsResponse,
)

logger = logging.getLogger(__name__)


class EntityDataServiceV2(EntityDataService):
    """v1 data service with the two record endpoints v2 implements re-pointed to v2."""

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
        """Build the v2 structured-query spec (always the ``v2`` endpoint)."""
        body = build_query_body(
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
        )
        params: dict[str, Any] = {}
        if expansion_level is not None:
            params["expansionLevel"] = expansion_level
        return RequestSpec(
            method="POST",
            endpoint=Endpoint(
                f"datafabric_/api/v2/EntityService/entity/{entity_key}/query"
            ),
            params=params,
            json=body,
        )

    @staticmethod
    def _get_record_spec(
        entity_key: str,
        record_id: str,
        expansion_level: Optional[int] = None,
    ) -> RequestSpec:
        """Build the v2 single-record read spec."""
        params: dict[str, Any] = {}
        if expansion_level is not None:
            params["expansionLevel"] = expansion_level
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(
                f"datafabric_/api/v2/EntityService/entity/{entity_key}/read/{record_id}"
            ),
            params=params,
        )


class EntitySchemaServiceV2(EntitySchemaService):
    """v1 schema service with entity listing re-pointed to the v2 endpoint."""

    @staticmethod
    def _list_entities_spec() -> RequestSpec:
        """Build the v2 list-entities spec."""
        return RequestSpec(method="GET", endpoint=Endpoint("datafabric_/api/v2/Entity"))


class EntitiesServiceV2(BaseService):
    """Service for UiPath Data Service entities using the **v2** API (preview).

    Exposes only the operations the v2 backend implements: structured queries
    (:meth:`retrieve_records`), single-record reads (:meth:`get_record`), and
    entity listing (:meth:`list_entities`). Responses use the v1 models.

    !!! warning "Preview Feature"
        This service is experimental and intentionally limited. Behavior and
        parameters are subject to change in future versions.
    """

    def __init__(
        self,
        config: UiPathApiConfig,
        execution_context: UiPathExecutionContext,
        folders_service: Optional[FolderService] = None,
        folders_map: Optional[dict[str, str]] = None,
        entity_name_overrides: Optional[dict[str, str]] = None,
        routing_context: Optional[QueryRoutingOverrideContext] = None,
    ) -> None:
        """Initialise the v2 facade and its underlying schema and data services."""
        super().__init__(config=config, execution_context=execution_context)
        self._folders_service = folders_service
        self._routing_strategy = create_routing_strategy(
            folders_map=folders_map,
            effective_entity_names=entity_name_overrides,
            routing_context=routing_context,
            folders_service=folders_service,
        )
        self._schema = EntitySchemaServiceV2(
            config=config,
            execution_context=execution_context,
            folders_service=folders_service,
        )
        self._data = EntityDataServiceV2(
            config=config,
            execution_context=execution_context,
            folders_service=folders_service,
            routing_strategy=self._routing_strategy,
        )

    @traced(name="list_entities", run_type="uipath")
    def list_entities(self) -> List[Entity]:
        """List all entities in Data Service (v2)."""
        return self._schema.list_entities()

    @traced(name="list_entities", run_type="uipath")
    async def list_entities_async(self) -> List[Entity]:
        """Async variant of :meth:`list_entities`."""
        return await self._schema.list_entities_async()

    @traced(name="entity_get_record", run_type="uipath")
    def get_record(
        self, entity_key: str, record_id: str, expansion_level: Optional[int] = None
    ) -> EntityRecord:
        """Fetch a single entity record by its id (v2)."""
        return self._data.get_record(
            entity_key, record_id, expansion_level=expansion_level
        )

    @traced(name="entity_get_record", run_type="uipath")
    async def get_record_async(
        self, entity_key: str, record_id: str, expansion_level: Optional[int] = None
    ) -> EntityRecord:
        """Async variant of :meth:`get_record`."""
        return await self._data.get_record_async(
            entity_key, record_id, expansion_level=expansion_level
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
    ) -> RetrieveEntityRecordsResponse:
        """Retrieve records with structured filters, sorting, and aggregates (v2)."""
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
    ) -> RetrieveEntityRecordsResponse:
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
        )
