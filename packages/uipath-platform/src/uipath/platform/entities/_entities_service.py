"""Public facade for the Data Fabric entities surface.

:class:`EntitiesService` keeps the existing ``sdk.entities.*`` API flat and
unchanged from a caller's perspective while delegating each operation to the
appropriate underlying service:

* :class:`EntitySchemaService` — entity definitions, choice set listings,
  create / delete / update-metadata lifecycle.
* :class:`EntityDataService` — record CRUD (single and batch), structured
  queries, attachments, choice-set values, bulk import, and federated SQL
  queries.

The facade additionally owns cross-cutting concerns such as agent entity-set
resolution.
"""

import logging
from typing import Any, Dict, List, Optional, Type

from httpx import Response
from uipath.core.tracing import traced

from ..common._base_service import BaseService
from ..common._bindings import _resource_overwrites
from ..common._config import UiPathApiConfig
from ..common._execution_context import UiPathExecutionContext
from ..orchestrator._folder_service import FolderService
from ._entity_data_service import EntityDataService, FileContent
from ._entity_resolution import (
    build_resolution_service,
    create_resolution_plan,
    create_resolution_plan_async,
    create_routing_strategy,
    fetch_resolved_entities,
    fetch_resolved_entities_async,
)
from ._entity_schema_service import EntitySchemaService
from .entities import (
    ChoiceSetValue,
    DataFabricEntityItem,
    Entity,
    EntityAggregate,
    EntityBinning,
    EntityCreateFieldOptions,
    EntityCreateOptions,
    EntityImportRecordsResponse,
    EntityJoin,
    EntityMetadataUpdateOptions,
    EntityQueryFilterGroup,
    EntityQuerySortOption,
    EntityRecord,
    EntityRecordsBatchResponse,
    EntityRecordsListResponse,
    EntitySetResolution,
    QueryRoutingOverrideContext,
    RetrieveEntityRecordsResponse,
)

logger = logging.getLogger(__name__)


class EntitiesService(BaseService):
    """Service for managing UiPath Data Service entities.

    Entities are database tables in UiPath Data Service that store structured
    data for automation processes. This service is the unified entry point for
    every entity operation: schema management, record CRUD, structured and
    SQL queries, file attachments, choice sets, and bulk import.

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
        folders_map: Optional[Dict[str, str]] = None,
        entity_name_overrides: Optional[Dict[str, str]] = None,
        routing_context: Optional[QueryRoutingOverrideContext] = None,
    ) -> None:
        """Initialise the facade and its underlying schema and data services."""
        super().__init__(config=config, execution_context=execution_context)
        self._folders_service = folders_service
        self._routing_strategy = create_routing_strategy(
            folders_map=folders_map,
            effective_entity_names=entity_name_overrides,
            routing_context=routing_context,
            folders_service=folders_service,
        )
        self._schema = EntitySchemaService(
            config=config,
            execution_context=execution_context,
            folders_service=folders_service,
        )
        self._data = EntityDataService(
            config=config,
            execution_context=execution_context,
            folders_service=folders_service,
            routing_strategy=self._routing_strategy,
        )

    # ------------------------------------------------------------------
    # Schema operations — delegate to EntitySchemaService
    # ------------------------------------------------------------------

    @traced(name="entity_retrieve", run_type="uipath")
    def retrieve(self, entity_key: str) -> Entity:
        """Retrieve an entity by its key.

        Args:
            entity_key (str): The unique key/identifier of the entity.

        Returns:
            Entity: The entity with all its metadata and field definitions, including:
                - name: Entity name
                - display_name: Human-readable display name
                - fields: List of field metadata (field names, types, constraints)
                - record_count: Number of records in the entity
                - storage_size_in_mb: Storage size used by the entity

        Examples:
            Basic usage::

                # Retrieve entity metadata
                entity = entities_service.retrieve("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
                print(f"Entity: {entity.display_name}")
                print(f"Records: {entity.record_count}")

            Inspecting entity fields::

                entity = entities_service.retrieve("a1b2c3d4-e5f6-7890-abcd-ef1234567890")

                # List all fields and their types
                for field in entity.fields:
                    print(f"{field.name} ({field.sql_type.name})")
                    print(f"  Required: {field.is_required}")
                    print(f"  Primary Key: {field.is_primary_key}")
        """
        return self._schema.retrieve(entity_key)

    @traced(name="entity_retrieve", run_type="uipath")
    async def retrieve_async(self, entity_key: str) -> Entity:
        """Asynchronously retrieve an entity by its key.

        Args:
            entity_key (str): The unique key/identifier of the entity.

        Returns:
            Entity: The entity with all its metadata and field definitions, including:
                - name: Entity name
                - display_name: Human-readable display name
                - fields: List of field metadata (field names, types, constraints)
                - record_count: Number of records in the entity
                - storage_size_in_mb: Storage size used by the entity

        Examples:
            Basic usage::

                # Retrieve entity metadata
                entity = await entities_service.retrieve_async("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
                print(f"Entity: {entity.display_name}")
                print(f"Records: {entity.record_count}")

            Inspecting entity fields::

                entity = await entities_service.retrieve_async("a1b2c3d4-e5f6-7890-abcd-ef1234567890")

                # List all fields and their types
                for field in entity.fields:
                    print(f"{field.name} ({field.sql_type.name})")
                    print(f"  Required: {field.is_required}")
                    print(f"  Primary Key: {field.is_primary_key}")
        """
        return await self._schema.retrieve_async(entity_key)

    @traced(name="entity_retrieve_by_name", run_type="uipath")
    def retrieve_by_name(
        self, entity_name: str, folder_key: Optional[str] = None
    ) -> Entity:
        """Retrieve an entity by its name.

        The server resolves the entity within the folder identified by
        ``folder_key``.  When omitted the default folder from the
        execution context is used.

        Args:
            entity_name: The name of the entity.
            folder_key: Optional folder key for disambiguation.
        """
        return self._schema.retrieve_by_name(entity_name, folder_key=folder_key)

    @traced(name="entity_retrieve_by_name", run_type="uipath")
    async def retrieve_by_name_async(
        self, entity_name: str, folder_key: Optional[str] = None
    ) -> Entity:
        """Asynchronously retrieve an entity by its name.

        The server resolves the entity within the folder identified by
        ``folder_key``.  When omitted the default folder from the
        execution context is used.

        Args:
            entity_name: The name of the entity.
            folder_key: Optional folder key for disambiguation.
        """
        return await self._schema.retrieve_by_name_async(
            entity_name, folder_key=folder_key
        )

    @traced(name="list_entities", run_type="uipath")
    def list_entities(self) -> List[Entity]:
        """List all entities in Data Service.

        Returns:
            List[Entity]: A list of all entities with their metadata and field definitions.
                Each entity includes name, display name, fields, record count, and storage information.

        Examples:
            List all entities::

                # Get all entities in the Data Service
                entities = entities_service.list_entities()
                for entity in entities:
                    print(f"{entity.display_name} ({entity.name})")

            Find entities with RBAC enabled::

                entities = entities_service.list_entities()

                # Filter to entities with row-based access control
                rbac_entities = [
                    e for e in entities
                    if e.is_rbac_enabled
                ]

            Summary report::

                entities = entities_service.list_entities()

                total_records = sum(e.record_count or 0 for e in entities)
                total_storage = sum(e.storage_size_in_mb or 0 for e in entities)

                print(f"Total entities: {len(entities)}")
                print(f"Total records: {total_records}")
                print(f"Total storage: {total_storage:.2f} MB")
        """
        return self._schema.list_entities()

    @traced(name="list_entities", run_type="uipath")
    async def list_entities_async(self) -> List[Entity]:
        """Asynchronously list all entities in the Data Service.

        Returns:
            List[Entity]: A list of all entities with their metadata and field definitions.
                Each entity includes name, display name, fields, record count, and storage information.

        Examples:
            List all entities::

                # Get all entities in the Data Service
                entities = await entities_service.list_entities_async()
                for entity in entities:
                    print(f"{entity.display_name} ({entity.name})")

            Find entities with RBAC enabled::

                entities = await entities_service.list_entities_async()

                # Filter to entities with row-based access control
                rbac_entities = [
                    e for e in entities
                    if e.is_rbac_enabled
                ]

            Summary report::

                entities = await entities_service.list_entities_async()

                total_records = sum(e.record_count or 0 for e in entities)
                total_storage = sum(e.storage_size_in_mb or 0 for e in entities)

                print(f"Total entities: {len(entities)}")
                print(f"Total records: {total_records}")
                print(f"Total storage: {total_storage:.2f} MB")
        """
        return await self._schema.list_entities_async()

    @traced(name="list_choicesets", run_type="uipath")
    def list_choicesets(self) -> List[Entity]:
        """List all choice sets in Data Service.

        Returns:
            List[Entity]: A list of all choice set entities.

        Examples:
            List all choice sets::

                choicesets = entities_service.list_choicesets()
                for cs in choicesets:
                    print(f"{cs.display_name} ({cs.id})")
        """
        return self._schema.list_choicesets()

    @traced(name="list_choicesets", run_type="uipath")
    async def list_choicesets_async(self) -> List[Entity]:
        """Asynchronously list all choice sets in Data Service.

        Returns:
            List[Entity]: A list of all choice set entities.
        """
        return await self._schema.list_choicesets_async()

    @traced(name="entity_create", run_type="uipath")
    def create_entity(
        self,
        name: str,
        fields: List[EntityCreateFieldOptions],
        options: Optional[EntityCreateOptions] = None,
    ) -> str:
        """Create a new entity with the given schema and return its id.

        Args:
            name (str): Entity name. Must start with a letter and contain
                only letters, digits, and underscores (3-100 characters).
            fields (List[EntityCreateFieldOptions]): Field definitions for
                the new entity. Each entry declares the field's name, type,
                and optional constraints such as ``length_limit``,
                ``decimal_precision``, ``is_required``, ``is_unique``, etc.
            options (Optional[EntityCreateOptions]): Optional entity-level
                settings such as display name, description, folder
                placement, and RBAC / analytics flags.

        Returns:
            str: The id (UUID) of the newly created entity.

        Raises:
            ValueError: If the entity name or any field name fails the
                client-side validation (regex / length / reserved names) or
                if a per-field constraint is not supported for that field
                type or is out of range.

        Examples:
            Create a simple entity::

                from uipath.platform.entities import (
                    EntityCreateFieldOptions,
                    EntityCreateOptions,
                    EntityFieldDataType,
                )

                entity_id = entities_service.create_entity(
                    "ProductCatalog",
                    [
                        EntityCreateFieldOptions(
                            field_name="product_name",
                            type=EntityFieldDataType.STRING,
                            is_required=True,
                            is_unique=True,
                        ),
                        EntityCreateFieldOptions(
                            field_name="price",
                            type=EntityFieldDataType.DECIMAL,
                            decimal_precision=2,
                        ),
                    ],
                    options=EntityCreateOptions(
                        display_name="Product Catalog",
                        description="Inventory of available products",
                        is_rbac_enabled=True,
                    ),
                )
        """
        return self._schema.create_entity(name, fields, options)

    @traced(name="entity_create", run_type="uipath")
    async def create_entity_async(
        self,
        name: str,
        fields: List[EntityCreateFieldOptions],
        options: Optional[EntityCreateOptions] = None,
    ) -> str:
        """Asynchronously create a new entity with the given schema.

        Args:
            name (str): Entity name; same validation rules as :meth:`create_entity`.
            fields (List[EntityCreateFieldOptions]): Field definitions.
            options (Optional[EntityCreateOptions]): Optional entity-level settings.

        Returns:
            str: The id (UUID) of the newly created entity.

        Raises:
            ValueError: For client-side validation failures.

        Examples:
            Create a simple entity::

                from uipath.platform.entities import (
                    EntityCreateFieldOptions,
                    EntityFieldDataType,
                )

                entity_id = await entities_service.create_entity_async(
                    "ProductCatalog",
                    [
                        EntityCreateFieldOptions(
                            field_name="product_name",
                            type=EntityFieldDataType.STRING,
                            is_required=True,
                        ),
                    ],
                )
        """
        return await self._schema.create_entity_async(name, fields, options)

    @traced(name="entity_delete", run_type="uipath")
    def delete_entity(self, entity_id: str) -> None:
        """Delete an entity and all of its records.

        Args:
            entity_id (str): The unique identifier of the entity to delete.

        Examples:
            Delete an entity by id::

                entities_service.delete_entity("a1b2c3d4-...")
        """
        self._schema.delete_entity(entity_id)

    @traced(name="entity_delete", run_type="uipath")
    async def delete_entity_async(self, entity_id: str) -> None:
        """Asynchronously delete an entity and all of its records.

        Args:
            entity_id (str): The unique identifier of the entity to delete.

        Examples:
            Delete an entity by id::

                await entities_service.delete_entity_async("a1b2c3d4-...")
        """
        await self._schema.delete_entity_async(entity_id)

    @traced(name="entity_update_metadata", run_type="uipath")
    def update_entity_metadata(
        self,
        entity_id: str,
        metadata: EntityMetadataUpdateOptions | Dict[str, Any],
    ) -> None:
        """Update an entity's display name, description, and/or RBAC flag.

        Args:
            entity_id (str): The unique identifier of the entity.
            metadata (EntityMetadataUpdateOptions | Dict[str, Any]):
                An :class:`EntityMetadataUpdateOptions` instance or a dict
                with any of ``display_name``, ``description``,
                ``is_rbac_enabled``. Dict keys may be snake_case
                (``display_name``) or camelCase (``displayName``); both
                serialize correctly to the API.

        Examples:
            Rename and update description::

                from uipath.platform.entities import EntityMetadataUpdateOptions

                entities_service.update_entity_metadata(
                    "a1b2c3d4-...",
                    EntityMetadataUpdateOptions(
                        display_name="New Display Name",
                        description="Refreshed description",
                    ),
                )

            From a plain dict::

                entities_service.update_entity_metadata(
                    "a1b2c3d4-...",
                    {"display_name": "X", "is_rbac_enabled": True},
                )
        """
        self._schema.update_entity_metadata(entity_id, metadata)

    @traced(name="entity_update_metadata", run_type="uipath")
    async def update_entity_metadata_async(
        self,
        entity_id: str,
        metadata: EntityMetadataUpdateOptions | Dict[str, Any],
    ) -> None:
        """Asynchronously update an entity's display name, description, and/or RBAC flag.

        Args:
            entity_id (str): The unique identifier of the entity.
            metadata (EntityMetadataUpdateOptions | Dict[str, Any]):
                An :class:`EntityMetadataUpdateOptions` instance or a dict
                with any of ``display_name``, ``description``,
                ``is_rbac_enabled``.

        Examples:
            Rename::

                from uipath.platform.entities import EntityMetadataUpdateOptions

                await entities_service.update_entity_metadata_async(
                    "a1b2c3d4-...",
                    EntityMetadataUpdateOptions(display_name="Renamed Entity"),
                )
        """
        await self._schema.update_entity_metadata_async(entity_id, metadata)

    # ------------------------------------------------------------------
    # Data operations — delegate to EntityDataService
    # ------------------------------------------------------------------

    @traced(name="get_choiceset_values", run_type="uipath")
    def get_choiceset_values(
        self,
        choiceset_id: str,
        start: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[ChoiceSetValue]:
        """Get the values of a choice set by its ID.

        Args:
            choiceset_id: The unique identifier of the choice set.
            start: Optional offset for pagination.
            limit: Optional page size for pagination.

        Returns:
            List[ChoiceSetValue]: The values in the choice set, each containing
                id, name, display_name, and number_id.

        Examples:
            Get all values in a choice set::

                values = entities_service.get_choiceset_values("choiceset-id")
                for v in values:
                    print(f"{v.number_id}: {v.display_name}")
        """
        return self._data.get_choiceset_values(choiceset_id, start=start, limit=limit)

    @traced(name="get_choiceset_values", run_type="uipath")
    async def get_choiceset_values_async(
        self,
        choiceset_id: str,
        start: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[ChoiceSetValue]:
        """Asynchronously get the values of a choice set by its ID.

        Args:
            choiceset_id: The unique identifier of the choice set.
            start: Optional offset for pagination.
            limit: Optional page size for pagination.

        Returns:
            List[ChoiceSetValue]: The values in the choice set.
        """
        return await self._data.get_choiceset_values_async(
            choiceset_id, start=start, limit=limit
        )

    @traced(name="entity_list_records", run_type="uipath")
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
        """List records from an entity with optional pagination and schema validation.

        The schema parameter enables type-safe access to entity records by validating the
        data against a user-defined class with type annotations. When provided, each record
        is validated against the schema's field definitions before being returned.

        Args:
            entity_key (str): The unique key/identifier of the entity.
            schema (Optional[Type[Any]]): Optional schema class for validation. This should be
                a Python class with type-annotated fields that match the entity's structure.

                Field Validation Rules:
                - Required fields: Use standard type annotations (e.g., `name: str`)
                - Optional fields: Use `Optional` or union with None (e.g., `age: Optional[int]` or `age: int | None`)
                - Field names must match the entity's field names (case-sensitive)
                - The 'Id' field is automatically validated and does not need to be included

                Example schema class::

                    class CustomerRecord:
                        name: str  # Required field
                        email: str  # Required field
                        age: Optional[int]  # Optional field
                        phone: str | None  # Optional field (Python 3.10+ syntax)

                Benefits of using schema:
                - Type safety: Ensures records match expected structure
                - Early validation: Catches data issues before processing
                - Documentation: Schema serves as clear contract for record structure
                - IDE support: Enables better autocomplete and type checking

                When schema validation fails, a `ValueError` is raised with details about
                the validation error (e.g., missing required fields, type mismatches).

            start (Optional[int]): Starting index for pagination (0-based).
            limit (Optional[int]): Maximum number of records to return.
            expansion_level (Optional[int]): Depth of foreign-key expansion in the
                response (``0`` means no expansion). Higher values inline related
                records up to that many hops.
            filter (Optional[str]): OData ``$filter`` expression
                (e.g. ``"status eq 'active'"``).
            orderby (Optional[str]): OData ``$orderby`` expression
                (e.g. ``"created_at desc"``).
            select (Optional[List[str]]): Column projection — field names to
                include (rendered as ``$select``).
            expand (Optional[List[str]]): Relationship names to expand inline
                (rendered as ``$expand``).

        Returns:
            EntityRecordsListResponse: A list-compatible response with
                ``total_count``, ``has_next_page`` and ``next_cursor`` pagination
                metadata. Iteration, indexing, and ``len()`` continue to work
                like a plain list of :class:`EntityRecord`.

        Raises:
            ValueError: If schema validation fails for any record, including cases where
                required fields are missing or field types don't match the schema.

        Examples:
            Basic usage without schema::

                # Retrieve all records from an entity
                records = entities_service.list_records("Customers")
                for record in records:
                    print(record.id)

            With pagination::

                # Get first 50 records
                records = entities_service.list_records("Customers", start=0, limit=50)
                print(f"Showing {len(records)} of {records.total_count} total")
                if records.has_next_page:
                    next_page = entities_service.list_records(
                        "Customers", start=50, limit=50
                    )

            With OData filter, sorting, projection, and expansion::

                records = entities_service.list_records(
                    "Customers",
                    filter="status eq 'active'",
                    orderby="created_at desc",
                    select=["name", "email", "status"],
                    expand=["company"],
                    expansion_level=1,
                )

            With schema validation::

                class CustomerRecord:
                    name: str
                    email: str
                    age: Optional[int]
                    is_active: bool

                # Records are validated against CustomerRecord schema
                records = entities_service.list_records(
                    "Customers",
                    schema=CustomerRecord
                )

                # Safe to access fields knowing they match the schema
                for record in records:
                    print(f"{record.name}: {record.email}")
        """
        return self._data.list_records(
            entity_key,
            schema=schema,
            start=start,
            limit=limit,
            expansion_level=expansion_level,
            filter=filter,
            orderby=orderby,
            select=select,
            expand=expand,
        )

    @traced(name="entity_list_records", run_type="uipath")
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
        """Asynchronously list records from an entity with optional pagination and schema validation.

        The schema parameter enables type-safe access to entity records by validating the
        data against a user-defined class with type annotations. When provided, each record
        is validated against the schema's field definitions before being returned.

        Args:
            entity_key (str): The unique key/identifier of the entity.
            schema (Optional[Type[Any]]): Optional schema class for validation. This should be
                a Python class with type-annotated fields that match the entity's structure.

                Field Validation Rules:
                - Required fields: Use standard type annotations (e.g., `name: str`)
                - Optional fields: Use `Optional` or union with None (e.g., `age: Optional[int]` or `age: int | None`)
                - Field names must match the entity's field names (case-sensitive)
                - The 'Id' field is automatically validated and does not need to be included

                Example schema class::

                    class CustomerRecord:
                        name: str  # Required field
                        email: str  # Required field
                        age: Optional[int]  # Optional field
                        phone: str | None  # Optional field (Python 3.10+ syntax)

                Benefits of using schema:
                - Type safety: Ensures records match expected structure
                - Early validation: Catches data issues before processing
                - Documentation: Schema serves as clear contract for record structure
                - IDE support: Enables better autocomplete and type checking

                When schema validation fails, a `ValueError` is raised with details about
                the validation error (e.g., missing required fields, type mismatches).

            start (Optional[int]): Starting index for pagination (0-based).
            limit (Optional[int]): Maximum number of records to return.
            expansion_level (Optional[int]): Depth of foreign-key expansion in the
                response (``0`` means no expansion). Higher values inline related
                records up to that many hops.
            filter (Optional[str]): OData ``$filter`` expression
                (e.g. ``"status eq 'active'"``).
            orderby (Optional[str]): OData ``$orderby`` expression
                (e.g. ``"created_at desc"``).
            select (Optional[List[str]]): Column projection — field names to
                include (rendered as ``$select``).
            expand (Optional[List[str]]): Relationship names to expand inline
                (rendered as ``$expand``).

        Returns:
            EntityRecordsListResponse: A list-compatible response with
                ``total_count``, ``has_next_page`` and ``next_cursor`` pagination
                metadata. Iteration, indexing, and ``len()`` continue to work
                like a plain list of :class:`EntityRecord`.

        Raises:
            ValueError: If schema validation fails for any record, including cases where
                required fields are missing or field types don't match the schema.

        Examples:
            Basic usage without schema::

                # Retrieve all records from an entity
                records = await entities_service.list_records_async("Customers")
                for record in records:
                    print(record.id)

            With pagination::

                # Get first 50 records
                records = await entities_service.list_records_async("Customers", start=0, limit=50)
                print(f"Showing {len(records)} of {records.total_count} total")
                if records.has_next_page:
                    next_page = await entities_service.list_records_async(
                        "Customers", start=50, limit=50
                    )

            With OData filter, sorting, projection, and expansion::

                records = await entities_service.list_records_async(
                    "Customers",
                    filter="status eq 'active'",
                    orderby="created_at desc",
                    select=["name", "email", "status"],
                    expand=["company"],
                    expansion_level=1,
                )

            With schema validation::

                class CustomerRecord:
                    name: str
                    email: str
                    age: Optional[int]
                    is_active: bool

                # Records are validated against CustomerRecord schema
                records = await entities_service.list_records_async(
                    "Customers",
                    schema=CustomerRecord
                )

                # Safe to access fields knowing they match the schema
                for record in records:
                    print(f"{record.name}: {record.email}")
        """
        return await self._data.list_records_async(
            entity_key,
            schema=schema,
            start=start,
            limit=limit,
            expansion_level=expansion_level,
            filter=filter,
            orderby=orderby,
            select=select,
            expand=expand,
        )

    @traced(name="entity_insert_record", run_type="uipath")
    def insert_record(
        self,
        entity_key: str,
        data: Any,
        expansion_level: Optional[int] = None,
    ) -> EntityRecord:
        """Insert a single record into an entity and return the inserted row.

        Note:
            Unlike :meth:`insert_records` (batch), this single-record endpoint
            fires Data Fabric trigger events. Use this method when triggers
            attached to the entity must run.

        Args:
            entity_key (str): The unique key/identifier of the entity.
            data (Any): Record payload — a dict, a Pydantic model, an
                :class:`EntityRecord`, or any object exposing ``__dict__``.
            expansion_level (Optional[int]): Depth of foreign-key expansion in
                the response (``0`` means no expansion).

        Returns:
            EntityRecord: The inserted record with its server-assigned ``Id``
                plus any expanded relationships.

        Examples:
            Insert from a dict::

                record = entities_service.insert_record(
                    "Customers",
                    {"name": "Alice", "email": "alice@example.com"},
                )
                print(record.id)

            Insert from a Pydantic model::

                class CustomerInput(BaseModel):
                    name: str
                    email: str

                record = entities_service.insert_record(
                    "Customers",
                    CustomerInput(name="Bob", email="bob@example.com"),
                    expansion_level=1,
                )
        """
        return self._data.insert_record(
            entity_key, data, expansion_level=expansion_level
        )

    @traced(name="entity_insert_record", run_type="uipath")
    async def insert_record_async(
        self,
        entity_key: str,
        data: Any,
        expansion_level: Optional[int] = None,
    ) -> EntityRecord:
        """Asynchronously insert a single record into an entity.

        Note:
            Unlike :meth:`insert_records_async` (batch), this single-record
            endpoint fires Data Fabric trigger events. Use this method when
            triggers attached to the entity must run.

        Args:
            entity_key (str): The unique key/identifier of the entity.
            data (Any): Record payload — a dict, a Pydantic model, an
                :class:`EntityRecord`, or any object exposing ``__dict__``.
            expansion_level (Optional[int]): Depth of foreign-key expansion in
                the response (``0`` means no expansion).

        Returns:
            EntityRecord: The inserted record with its server-assigned ``Id``.

        Examples:
            Insert from a dict::

                record = await entities_service.insert_record_async(
                    "Customers",
                    {"name": "Alice", "email": "alice@example.com"},
                )
                print(record.id)
        """
        return await self._data.insert_record_async(
            entity_key, data, expansion_level=expansion_level
        )

    @traced(name="entity_get_record", run_type="uipath")
    def get_record(
        self,
        entity_key: str,
        record_id: str,
        expansion_level: Optional[int] = None,
    ) -> EntityRecord:
        """Fetch a single entity record by its id.

        Args:
            entity_key (str): The unique key/identifier of the entity.
            record_id (str): The unique identifier of the record to fetch.
            expansion_level (Optional[int]): Depth of foreign-key expansion in
                the response (``0`` means no expansion).

        Returns:
            EntityRecord: The record, with optional expanded relationships.

        Examples:
            Basic usage::

                record = entities_service.get_record("Customers", "rec-1")
                print(record.id, record.name)

            With FK expansion::

                # Inline the related Company record on the returned Customer
                record = entities_service.get_record(
                    "Customers", "rec-1", expansion_level=1
                )
        """
        return self._data.get_record(
            entity_key, record_id, expansion_level=expansion_level
        )

    @traced(name="entity_get_record", run_type="uipath")
    async def get_record_async(
        self,
        entity_key: str,
        record_id: str,
        expansion_level: Optional[int] = None,
    ) -> EntityRecord:
        """Asynchronously fetch a single entity record by its id.

        Args:
            entity_key (str): The unique key/identifier of the entity.
            record_id (str): The unique identifier of the record to fetch.
            expansion_level (Optional[int]): Depth of foreign-key expansion in
                the response (``0`` means no expansion).

        Returns:
            EntityRecord: The record.

        Examples:
            Basic usage::

                record = await entities_service.get_record_async("Customers", "rec-1")
                print(record.id, record.name)
        """
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
    ) -> EntityRecord:
        """Update a single record by id and return the updated row.

        Note:
            Unlike :meth:`update_records` (batch), this single-record endpoint
            fires Data Fabric trigger events. Use this method when triggers
            attached to the entity must run.

        Args:
            entity_key (str): The unique key/identifier of the entity.
            record_id (str): The unique identifier of the record to update.
            data (Any): Fields to update — a dict, a Pydantic model, or any
                object exposing ``__dict__``. Fields explicitly set to
                ``None`` are sent through; unset fields are omitted.
            expansion_level (Optional[int]): Depth of foreign-key expansion in
                the response (``0`` means no expansion).

        Returns:
            EntityRecord: The updated record.

        Examples:
            Partial update from a dict::

                record = entities_service.update_record(
                    "Customers",
                    "rec-1",
                    {"email": "alice.new@example.com"},
                )

            Clear a field by passing an explicit ``None``::

                # Note: unset fields are omitted; explicit None values are sent.
                record = entities_service.update_record(
                    "Customers",
                    "rec-1",
                    {"middle_name": None},
                )
        """
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
    ) -> EntityRecord:
        """Asynchronously update a single record by id.

        Note:
            Unlike :meth:`update_records_async` (batch), this single-record
            endpoint fires Data Fabric trigger events.

        Args:
            entity_key (str): The unique key/identifier of the entity.
            record_id (str): The unique identifier of the record to update.
            data (Any): Fields to update — a dict, a Pydantic model, or any
                object exposing ``__dict__``.
            expansion_level (Optional[int]): Depth of foreign-key expansion.

        Returns:
            EntityRecord: The updated record.

        Examples:
            Partial update::

                record = await entities_service.update_record_async(
                    "Customers",
                    "rec-1",
                    {"email": "alice.new@example.com"},
                )
        """
        return await self._data.update_record_async(
            entity_key, record_id, data, expansion_level=expansion_level
        )

    @traced(name="entity_delete_record", run_type="uipath")
    def delete_record(self, entity_key: str, record_id: str) -> None:
        """Delete a single record by id.

        Note:
            Unlike :meth:`delete_records` (batch), this single-record endpoint
            fires Data Fabric trigger events. Use this method when triggers
            attached to the entity must run on delete.

        Args:
            entity_key (str): The unique key/identifier of the entity.
            record_id (str): The unique identifier of the record to delete.

        Examples:
            Delete by id::

                entities_service.delete_record("Customers", "rec-1")
        """
        self._data.delete_record(entity_key, record_id)

    @traced(name="entity_delete_record", run_type="uipath")
    async def delete_record_async(self, entity_key: str, record_id: str) -> None:
        """Asynchronously delete a single record by id.

        Note:
            Unlike :meth:`delete_records_async` (batch), this single-record
            endpoint fires Data Fabric trigger events.

        Args:
            entity_key (str): The unique key/identifier of the entity.
            record_id (str): The unique identifier of the record to delete.

        Examples:
            Delete by id::

                await entities_service.delete_record_async("Customers", "rec-1")
        """
        await self._data.delete_record_async(entity_key, record_id)

    @traced(name="entity_record_insert_batch", run_type="uipath")
    def insert_records(
        self,
        entity_key: str,
        records: List[Any],
        schema: Optional[Type[Any]] = None,
        expansion_level: Optional[int] = None,
        fail_on_first: Optional[bool] = None,
    ) -> EntityRecordsBatchResponse:
        """Insert multiple records into an entity in a single batch operation.

        Args:
            entity_key (str): The unique key/identifier of the entity.
            records (List[Any]): List of records to insert. Each record may be
                a dict, a Pydantic model, an :class:`EntityRecord`, or any
                object exposing ``__dict__``.
            schema (Optional[Type[Any]]): Optional schema class for validation. When provided,
                validates that each record in the response matches the schema structure.
            expansion_level (Optional[int]): Depth of foreign-key expansion in
                the response (``0`` means no expansion).
            fail_on_first (Optional[bool]): When ``True``, stop the batch on
                the first per-record failure. When ``False`` (default), all
                records are attempted and the response lists both
                ``success_records`` and ``failure_records``.

        Returns:
            EntityRecordsBatchResponse: Response containing successful and failed record operations.
                - success_records: List of successfully inserted :class:`EntityRecord` objects
                - failure_records: List of :class:`FailureRecord` describing per-record errors

        Examples:
            Insert records without schema::

                class Customer:
                    def __init__(self, name, email, age):
                        self.name = name
                        self.email = email
                        self.age = age

                customers = [
                    Customer("John Doe", "john@example.com", 30),
                    Customer("Jane Smith", "jane@example.com", 25),
                ]

                response = entities_service.insert_records(
                    "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                    customers
                )

                print(f"Inserted: {len(response.success_records)}")
                print(f"Failed: {len(response.failure_records)}")

            Insert with FK expansion and fail-fast::

                response = entities_service.insert_records(
                    "Orders",
                    [{"product_id": "p-1", "qty": 3}, {"product_id": "p-2", "qty": 1}],
                    expansion_level=1,    # inline the related Product on each response record
                    fail_on_first=True,   # abort the batch at the first error
                )

            Insert with schema validation::

                class CustomerSchema:
                    name: str
                    email: str
                    age: int

                class Customer:
                    def __init__(self, name, email, age):
                        self.name = name
                        self.email = email
                        self.age = age

                customers = [Customer("Alice Brown", "alice@example.com", 28)]

                response = entities_service.insert_records(
                    "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                    customers,
                    schema=CustomerSchema
                )

                # Access inserted records with validated structure
                for record in response.success_records:
                    print(f"Inserted: {record.name} (ID: {record.id})")
        """
        return self._data.insert_records(
            entity_key,
            records,
            schema=schema,
            expansion_level=expansion_level,
            fail_on_first=fail_on_first,
        )

    @traced(name="entity_record_insert_batch", run_type="uipath")
    async def insert_records_async(
        self,
        entity_key: str,
        records: List[Any],
        schema: Optional[Type[Any]] = None,
        expansion_level: Optional[int] = None,
        fail_on_first: Optional[bool] = None,
    ) -> EntityRecordsBatchResponse:
        """Asynchronously insert multiple records into an entity in a single batch operation.

        Args:
            entity_key (str): The unique key/identifier of the entity.
            records (List[Any]): List of records to insert. Each record may be
                a dict, a Pydantic model, an :class:`EntityRecord`, or any
                object exposing ``__dict__``.
            schema (Optional[Type[Any]]): Optional schema class for validation. When provided,
                validates that each record in the response matches the schema structure.
            expansion_level (Optional[int]): Depth of foreign-key expansion in
                the response (``0`` means no expansion).
            fail_on_first (Optional[bool]): When ``True``, stop the batch on
                the first per-record failure. When ``False`` (default), all
                records are attempted and the response lists both
                ``success_records`` and ``failure_records``.

        Returns:
            EntityRecordsBatchResponse: Response containing successful and failed record operations.
                - success_records: List of successfully inserted :class:`EntityRecord` objects
                - failure_records: List of :class:`FailureRecord` describing per-record errors

        Examples:
            Insert records without schema::

                class Customer:
                    def __init__(self, name, email, age):
                        self.name = name
                        self.email = email
                        self.age = age

                customers = [
                    Customer("John Doe", "john@example.com", 30),
                    Customer("Jane Smith", "jane@example.com", 25),
                ]

                response = await entities_service.insert_records_async(
                    "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                    customers
                )

                print(f"Inserted: {len(response.success_records)}")
                print(f"Failed: {len(response.failure_records)}")

            Insert with schema validation::

                class CustomerSchema:
                    name: str
                    email: str
                    age: int

                class Customer:
                    def __init__(self, name, email, age):
                        self.name = name
                        self.email = email
                        self.age = age

                customers = [Customer("Alice Brown", "alice@example.com", 28)]

                response = await entities_service.insert_records_async(
                    "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                    customers,
                    schema=CustomerSchema
                )

                # Access inserted records with validated structure
                for record in response.success_records:
                    print(f"Inserted: {record.name} (ID: {record.id})")
        """
        return await self._data.insert_records_async(
            entity_key,
            records,
            schema=schema,
            expansion_level=expansion_level,
            fail_on_first=fail_on_first,
        )

    @traced(name="entity_record_update_batch", run_type="uipath")
    def update_records(
        self,
        entity_key: str,
        records: List[Any],
        schema: Optional[Type[Any]] = None,
        expansion_level: Optional[int] = None,
        fail_on_first: Optional[bool] = None,
    ) -> EntityRecordsBatchResponse:
        """Update multiple records in an entity in a single batch operation.

        Args:
            entity_key (str): The unique key/identifier of the entity.
            records (List[Any]): List of records to update. Each record must
                include its ``Id`` field. A record may be a dict, a Pydantic
                model, an :class:`EntityRecord`, or any object exposing
                ``__dict__``.
            schema (Optional[Type[Any]]): Optional schema class for validation. When provided,
                validates that each record in the request and response matches the schema structure.
            expansion_level (Optional[int]): Depth of foreign-key expansion in
                the response (``0`` means no expansion).
            fail_on_first (Optional[bool]): When ``True``, stop the batch on
                the first per-record failure. When ``False`` (default), all
                records are attempted and the response lists both
                ``success_records`` and ``failure_records``.

        Returns:
            EntityRecordsBatchResponse: Response containing successful and failed record operations.
                - success_records: List of successfully updated :class:`EntityRecord` objects
                - failure_records: List of :class:`FailureRecord` describing per-record errors

        Examples:
            Update records::

                # First, retrieve records to update
                records = entities_service.list_records("a1b2c3d4-e5f6-7890-abcd-ef1234567890")

                # Modify the records
                for record in records:
                    if record.name == "John Doe":
                        record.age = 31

                # Update the modified records
                response = entities_service.update_records(
                    "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                    records
                )

                print(f"Updated: {len(response.success_records)}")
                print(f"Failed: {len(response.failure_records)}")

            Update with schema validation::

                class CustomerSchema:
                    name: str
                    email: str
                    age: int

                # Retrieve and update
                records = entities_service.list_records(
                    "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                    schema=CustomerSchema
                )

                # Modify specific records
                for record in records:
                    if record.age < 30:
                        record.is_active = True

                response = entities_service.update_records(
                    "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                    records,
                    schema=CustomerSchema
                )

                for record in response.success_records:
                    print(f"Updated: {record.name}")
        """
        return self._data.update_records(
            entity_key,
            records,
            schema=schema,
            expansion_level=expansion_level,
            fail_on_first=fail_on_first,
        )

    @traced(name="entity_record_update_batch", run_type="uipath")
    async def update_records_async(
        self,
        entity_key: str,
        records: List[Any],
        schema: Optional[Type[Any]] = None,
        expansion_level: Optional[int] = None,
        fail_on_first: Optional[bool] = None,
    ) -> EntityRecordsBatchResponse:
        """Asynchronously update multiple records in an entity in a single batch operation.

        Args:
            entity_key (str): The unique key/identifier of the entity.
            records (List[Any]): List of records to update. Each record must
                include its ``Id`` field. A record may be a dict, a Pydantic
                model, an :class:`EntityRecord`, or any object exposing
                ``__dict__``.
            schema (Optional[Type[Any]]): Optional schema class for validation. When provided,
                validates that each record in the request and response matches the schema structure.
            expansion_level (Optional[int]): Depth of foreign-key expansion in
                the response (``0`` means no expansion).
            fail_on_first (Optional[bool]): When ``True``, stop the batch on
                the first per-record failure. When ``False`` (default), all
                records are attempted and the response lists both
                ``success_records`` and ``failure_records``.

        Returns:
            EntityRecordsBatchResponse: Response containing successful and failed record operations.
                - success_records: List of successfully updated :class:`EntityRecord` objects
                - failure_records: List of :class:`FailureRecord` describing per-record errors

        Examples:
            Update records::

                # First, retrieve records to update
                records = await entities_service.list_records_async("a1b2c3d4-e5f6-7890-abcd-ef1234567890")

                # Modify the records
                for record in records:
                    if record.name == "John Doe":
                        record.age = 31

                # Update the modified records
                response = await entities_service.update_records_async(
                    "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                    records
                )

                print(f"Updated: {len(response.success_records)}")
                print(f"Failed: {len(response.failure_records)}")

            Update with schema validation::

                class CustomerSchema:
                    name: str
                    email: str
                    age: int

                # Retrieve and update
                records = await entities_service.list_records_async(
                    "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                    schema=CustomerSchema
                )

                # Modify specific records
                for record in records:
                    if record.age < 30:
                        record.is_active = True

                response = await entities_service.update_records_async(
                    "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                    records,
                    schema=CustomerSchema
                )

                for record in response.success_records:
                    print(f"Updated: {record.name}")
        """
        return await self._data.update_records_async(
            entity_key,
            records,
            schema=schema,
            expansion_level=expansion_level,
            fail_on_first=fail_on_first,
        )

    @traced(name="entity_record_delete_batch", run_type="uipath")
    def delete_records(
        self,
        entity_key: str,
        record_ids: List[str],
        fail_on_first: Optional[bool] = None,
    ) -> EntityRecordsBatchResponse:
        """Delete multiple records from an entity in a single batch operation.

        Args:
            entity_key (str): The unique key/identifier of the entity.
            record_ids (List[str]): List of record IDs (GUIDs) to delete.
            fail_on_first (Optional[bool]): When ``True``, stop the batch on
                the first per-record failure. When ``False`` (default), all
                records are attempted and the response lists both
                ``success_records`` and ``failure_records``.

        Returns:
            EntityRecordsBatchResponse: Response containing successful and failed record operations.
                - success_records: List of successfully deleted :class:`EntityRecord` objects
                - failure_records: List of :class:`FailureRecord` describing per-record errors

        Examples:
            Delete specific records by ID::

                # Delete records by their IDs
                record_ids = [
                    "12345678-1234-1234-1234-123456789012",
                    "87654321-4321-4321-4321-210987654321",
                ]

                response = entities_service.delete_records(
                    "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                    record_ids
                )

                print(f"Deleted: {len(response.success_records)}")
                print(f"Failed: {len(response.failure_records)}")

            Delete records matching a condition::

                # Get all records
                records = entities_service.list_records("a1b2c3d4-e5f6-7890-abcd-ef1234567890")

                # Filter records to delete (e.g., inactive customers)
                ids_to_delete = [
                    record.id for record in records
                    if not getattr(record, 'is_active', True)
                ]

                if ids_to_delete:
                    response = entities_service.delete_records(
                        "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                        ids_to_delete
                    )
                    print(f"Deleted {len(response.success_records)} inactive records")
        """
        return self._data.delete_records(
            entity_key, record_ids, fail_on_first=fail_on_first
        )

    @traced(name="entity_record_delete_batch", run_type="uipath")
    async def delete_records_async(
        self,
        entity_key: str,
        record_ids: List[str],
        fail_on_first: Optional[bool] = None,
    ) -> EntityRecordsBatchResponse:
        """Asynchronously delete multiple records from an entity in a single batch operation.

        Args:
            entity_key (str): The unique key/identifier of the entity.
            record_ids (List[str]): List of record IDs (GUIDs) to delete.
            fail_on_first (Optional[bool]): When ``True``, stop the batch on
                the first per-record failure. When ``False`` (default), all
                records are attempted and the response lists both
                ``success_records`` and ``failure_records``.

        Returns:
            EntityRecordsBatchResponse: Response containing successful and failed record operations.
                - success_records: List of successfully deleted :class:`EntityRecord` objects
                - failure_records: List of :class:`FailureRecord` describing per-record errors

        Examples:
            Delete specific records by ID::

                # Delete records by their IDs
                record_ids = [
                    "12345678-1234-1234-1234-123456789012",
                    "87654321-4321-4321-4321-210987654321",
                ]

                response = await entities_service.delete_records_async(
                    "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                    record_ids
                )

                print(f"Deleted: {len(response.success_records)}")
                print(f"Failed: {len(response.failure_records)}")

            Delete records matching a condition::

                # Get all records
                records = await entities_service.list_records_async("a1b2c3d4-e5f6-7890-abcd-ef1234567890")

                # Filter records to delete (e.g., inactive customers)
                ids_to_delete = [
                    record.id for record in records
                    if not getattr(record, 'is_active', True)
                ]

                if ids_to_delete:
                    response = await entities_service.delete_records_async(
                        "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                        ids_to_delete
                    )
                    print(f"Deleted {len(response.success_records)} inactive records")
        """
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
    ) -> RetrieveEntityRecordsResponse:
        """Retrieve records with structured filters, sorting, expansion, joins, and aggregates.

        Routes to the V2 endpoint when ``binnings`` is provided (numeric/date
        binning is gated by the ``enable-binning-on-query`` feature flag on
        the backend).

        Args:
            entity_key (str): The unique key/identifier of the entity.
            filter_group (Optional[EntityQueryFilterGroup]): Nested filter
                conditions combined with AND/OR.
            sort_options (Optional[List[EntityQuerySortOption]]): Sort fields
                and direction.
            selected_fields (Optional[List[str]]): Column projection — field
                names to include; omit to return all fields.
            expansions (Optional[List[Any]]): Foreign-key relationships to
                expand inline on each result record.
            expansion_level (Optional[int]): Depth of expansion (sent as a
                URL query param).
            aggregates (Optional[List[EntityAggregate]]): Aggregate
                expressions (``COUNT`` / ``SUM`` / ``AVG`` / ``MIN`` /
                ``MAX``). Maximum 5 per query.
            group_by (Optional[List[str]]): Fields to group aggregate results
                by. Maximum 5; required when both ``aggregates`` and
                ``selected_fields`` are supplied.
            joins (Optional[List[EntityJoin]]): Cross-entity joins. Maximum
                3, all of the same type.
            binnings (Optional[List[EntityBinning]]): Bucket numeric or date
                group-by fields. Each entry's field must also appear in
                ``group_by``.
            start (Optional[int]): Records to skip (pagination offset).
            limit (Optional[int]): Maximum number of records to return.

        Returns:
            RetrieveEntityRecordsResponse: A response with ``items``,
                ``total_count``, ``has_next_page``, and ``next_cursor``.
                ``items`` is a list of :class:`EntityRecord` for plain
                queries, or :class:`AggregateRow` when ``aggregates``,
                ``group_by``, or ``binnings`` are used. ``next_cursor`` is
                populated only when the backend returns one; otherwise
                paginate by passing the next ``start``.

        Examples:
            Filter + sort + projection::

                from uipath.platform.entities import (
                    EntityQueryFilter,
                    EntityQueryFilterGroup,
                    EntityQuerySortOption,
                    LogicalOperator,
                    QueryFilterOperator,
                )

                result = entities_service.retrieve_records(
                    "Customers",
                    filter_group=EntityQueryFilterGroup(
                        logical_operator=LogicalOperator.And,
                        query_filters=[
                            EntityQueryFilter(
                                field_name="status",
                                operator=QueryFilterOperator.Equals,
                                value="active",
                            )
                        ],
                    ),
                    sort_options=[
                        EntityQuerySortOption(field_name="created_at", is_descending=True)
                    ],
                    selected_fields=["Id", "name", "email"],
                    start=0,
                    limit=50,
                )
                print(f"Found {result.total_count} customers")

            Aggregates and group-by (counts per status)::

                from uipath.platform.entities import (
                    EntityAggregate,
                    EntityAggregateFunction,
                )

                result = entities_service.retrieve_records(
                    "Customers",
                    selected_fields=["status"],
                    group_by=["status"],
                    aggregates=[
                        EntityAggregate(
                            function=EntityAggregateFunction.Count,
                            field="Id",
                            alias="total",
                        )
                    ],
                )
                for row in result.items:
                    print(row.status, row.total)
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
        """Asynchronously retrieve records with structured filters, sorting, expansion, joins, and aggregates.

        Routes to the V2 endpoint when ``binnings`` is provided (numeric/date
        binning is gated by the ``enable-binning-on-query`` feature flag on
        the backend).

        Args:
            entity_key (str): The unique key/identifier of the entity.
            filter_group (Optional[EntityQueryFilterGroup]): Nested filter
                conditions combined with AND/OR.
            sort_options (Optional[List[EntityQuerySortOption]]): Sort fields
                and direction.
            selected_fields (Optional[List[str]]): Column projection — field
                names to include; omit to return all fields.
            expansions (Optional[List[Any]]): Foreign-key relationships to
                expand inline on each result record.
            expansion_level (Optional[int]): Depth of expansion.
            aggregates (Optional[List[EntityAggregate]]): Aggregate
                expressions. Maximum 5 per query.
            group_by (Optional[List[str]]): Fields to group aggregate results
                by. Maximum 5; required when both ``aggregates`` and
                ``selected_fields`` are supplied.
            joins (Optional[List[EntityJoin]]): Cross-entity joins. Maximum
                3, all of the same type.
            binnings (Optional[List[EntityBinning]]): Bucket numeric or date
                group-by fields.
            start (Optional[int]): Records to skip (pagination offset).
            limit (Optional[int]): Maximum number of records to return.

        Returns:
            RetrieveEntityRecordsResponse: A response with ``items``,
                ``total_count``, ``has_next_page``, and ``next_cursor``.

        Examples:
            Filter + sort + pagination::

                from uipath.platform.entities import (
                    EntityQueryFilter,
                    EntityQueryFilterGroup,
                    QueryFilterOperator,
                )

                result = await entities_service.retrieve_records_async(
                    "Customers",
                    filter_group=EntityQueryFilterGroup(
                        query_filters=[
                            EntityQueryFilter(
                                field_name="status",
                                operator=QueryFilterOperator.Equals,
                                value="active",
                            )
                        ],
                    ),
                    start=0,
                    limit=25,
                )
                print(f"{len(result.items)} of {result.total_count} customers")
        """
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

    @traced(name="entity_query_records", run_type="uipath")
    def query_entity_records(self, sql_query: str) -> List[Dict[str, Any]]:
        """Query entity records using a validated SQL query.

        PREVIEW: This method is in preview and may change in future releases.

        Args:
            sql_query (str): A SQL SELECT query to execute against Data Service entities.
                Only SELECT statements are allowed. Queries without WHERE must include
                a LIMIT clause. Subqueries and multi-statement queries are not permitted.

        Notes:
            A routing context is always derived from the configured ``folders_map``
            when present and included in the request body.

        Returns:
            List[Dict[str, Any]]: A list of result records as dictionaries.

        Raises:
            ValueError: If the SQL query fails validation (e.g., non-SELECT, missing
                WHERE/LIMIT, forbidden keywords, subqueries).
        """
        return self._data.query_entity_records(sql_query)

    @traced(name="entity_query_records", run_type="uipath")
    async def query_entity_records_async(self, sql_query: str) -> List[Dict[str, Any]]:
        """Asynchronously query entity records using a validated SQL query.

        PREVIEW: This method is in preview and may change in future releases.

        Args:
            sql_query (str): A SQL SELECT query to execute against Data Service entities.
                Only SELECT statements are allowed. Queries without WHERE must include
                a LIMIT clause. Subqueries and multi-statement queries are not permitted.

        Notes:
            A routing context is always derived from the configured ``folders_map``
            when present and included in the request body.

        Returns:
            List[Dict[str, Any]]: A list of result records as dictionaries.

        Raises:
            ValueError: If the SQL query fails validation (e.g., non-SELECT, missing
                WHERE/LIMIT, forbidden keywords, subqueries).
        """
        return await self._data.query_entity_records_async(sql_query)

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
        """Upload a file attachment to a File-type field on a record.

        Provide exactly one of ``file`` (raw bytes) or ``file_path`` (path on
        disk).

        Args:
            entity_id (str): The unique identifier of the entity.
            record_id (str): The unique identifier of the record whose
                attachment field is being set.
            field_name (str): Name of the File-type field on the entity.
            file (Optional[FileContent]): Raw bytes (``bytes`` /
                ``bytearray`` / ``memoryview``) of the file to upload.
                Mutually exclusive with ``file_path``.
            file_path (Optional[str]): Path to a local file to upload.
                Mutually exclusive with ``file``.
            expansion_level (Optional[int]): Optional FK expansion depth in
                the response (``0`` means no expansion).

        Returns:
            Dict[str, Any]: The decoded JSON response (typically the updated
                record), or an empty dict when the response has no body.

        Examples:
            Upload from raw bytes::

                with open("contract.pdf", "rb") as f:
                    data = f.read()
                entities_service.upload_attachment(
                    "Customers", "rec-1", "Contract", file=data
                )

            Upload from a path on disk::

                entities_service.upload_attachment(
                    "Customers", "rec-1", "Contract", file_path="./contract.pdf"
                )
        """
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
        """Asynchronously upload a file attachment to a File-type field on a record.

        Provide exactly one of ``file`` (raw bytes) or ``file_path`` (path on
        disk).

        Args:
            entity_id (str): The unique identifier of the entity.
            record_id (str): The unique identifier of the record whose
                attachment field is being set.
            field_name (str): Name of the File-type field on the entity.
            file (Optional[FileContent]): Raw bytes of the file to upload.
                Mutually exclusive with ``file_path``.
            file_path (Optional[str]): Path to a local file to upload.
                Mutually exclusive with ``file``.
            expansion_level (Optional[int]): Optional FK expansion depth in
                the response.

        Returns:
            Dict[str, Any]: The decoded JSON response.

        Examples:
            Upload from a path on disk::

                await entities_service.upload_attachment_async(
                    "Customers", "rec-1", "Contract", file_path="./contract.pdf"
                )
        """
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
        """Download a file attached to a record and return its raw bytes.

        Args:
            entity_id (str): The unique identifier of the entity.
            record_id (str): The unique identifier of the record containing
                the attachment.
            field_name (str): Name of the File-type field on the entity.

        Returns:
            bytes: The raw file content.

        Examples:
            Save the downloaded bytes to disk::

                content = entities_service.download_attachment(
                    "Customers", "rec-1", "Contract"
                )
                with open("downloaded.pdf", "wb") as f:
                    f.write(content)
        """
        return self._data.download_attachment(entity_id, record_id, field_name)

    @traced(name="entity_download_attachment", run_type="uipath")
    async def download_attachment_async(
        self, entity_id: str, record_id: str, field_name: str
    ) -> bytes:
        """Asynchronously download a file attached to a record.

        Args:
            entity_id (str): The unique identifier of the entity.
            record_id (str): The unique identifier of the record containing
                the attachment.
            field_name (str): Name of the File-type field on the entity.

        Returns:
            bytes: The raw file content.

        Examples:
            Save the downloaded bytes to disk::

                content = await entities_service.download_attachment_async(
                    "Customers", "rec-1", "Contract"
                )
                with open("downloaded.pdf", "wb") as f:
                    f.write(content)
        """
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
        """Remove the file attached to a File-type field on a record.

        Args:
            entity_id (str): The unique identifier of the entity.
            record_id (str): The unique identifier of the record whose
                attachment is being removed.
            field_name (str): Name of the File-type field on the entity.
            expansion_level (Optional[int]): Optional FK expansion depth in
                the response (``0`` means no expansion).

        Returns:
            Dict[str, Any]: The decoded JSON response (typically the updated
                record), or an empty dict when the response has no body.

        Examples:
            Clear an attachment::

                entities_service.delete_attachment(
                    "Customers", "rec-1", "Contract"
                )
        """
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
        """Asynchronously remove the file attached to a File-type field.

        Args:
            entity_id (str): The unique identifier of the entity.
            record_id (str): The unique identifier of the record whose
                attachment is being removed.
            field_name (str): Name of the File-type field on the entity.
            expansion_level (Optional[int]): Optional FK expansion depth.

        Returns:
            Dict[str, Any]: The decoded JSON response.

        Examples:
            Clear an attachment::

                await entities_service.delete_attachment_async(
                    "Customers", "rec-1", "Contract"
                )
        """
        return await self._data.delete_attachment_async(
            entity_id, record_id, field_name, expansion_level=expansion_level
        )

    @traced(name="entity_import_records", run_type="uipath")
    def import_records(
        self,
        entity_id: str,
        file: Optional[FileContent] = None,
        file_path: Optional[str] = None,
    ) -> EntityImportRecordsResponse:
        """Bulk-import records into an entity from a CSV file.

        Provide exactly one of ``file`` (raw bytes) or ``file_path`` (path on
        disk).

        Args:
            entity_id (str): The unique identifier of the entity.
            file (Optional[FileContent]): Raw bytes of a CSV file. Mutually
                exclusive with ``file_path``.
            file_path (Optional[str]): Path to a local CSV file. Mutually
                exclusive with ``file``.

        Returns:
            EntityImportRecordsResponse: Reports the total rows in the file,
                the number successfully inserted, and an optional
                ``error_file_link`` pointing to a CSV listing rows that
                failed validation.

        Examples:
            Import from a path on disk::

                result = entities_service.import_records(
                    "Customers", file_path="./customers.csv"
                )
                print(
                    f"Inserted {result.inserted_records} of "
                    f"{result.total_records} rows"
                )
                if result.error_file_link:
                    print(f"Errors: {result.error_file_link}")
        """
        return self._data.import_records(entity_id, file=file, file_path=file_path)

    @traced(name="entity_import_records", run_type="uipath")
    async def import_records_async(
        self,
        entity_id: str,
        file: Optional[FileContent] = None,
        file_path: Optional[str] = None,
    ) -> EntityImportRecordsResponse:
        """Asynchronously bulk-import records into an entity from a CSV file.

        Provide exactly one of ``file`` (raw bytes) or ``file_path`` (path on
        disk).

        Args:
            entity_id (str): The unique identifier of the entity.
            file (Optional[FileContent]): Raw bytes of a CSV file.
            file_path (Optional[str]): Path to a local CSV file.

        Returns:
            EntityImportRecordsResponse: Reports the total, inserted, and
                ``error_file_link`` for failed rows.

        Examples:
            Import from a path on disk::

                result = await entities_service.import_records_async(
                    "Customers", file_path="./customers.csv"
                )
                print(
                    f"Inserted {result.inserted_records} of "
                    f"{result.total_records} rows"
                )
        """
        return await self._data.import_records_async(
            entity_id, file=file, file_path=file_path
        )

    # ------------------------------------------------------------------
    # Public helper retained for backward compatibility — tests call this
    # ------------------------------------------------------------------

    def validate_entity_batch(
        self,
        batch_response: Response,
        schema: Optional[Type[Any]] = None,
    ) -> EntityRecordsBatchResponse:
        """Parse a batch response, optionally validating success records against ``schema``.

        Failure records are returned as :class:`FailureRecord` instances and
        are not validated against the user schema.
        """
        return self._data.validate_entity_batch(batch_response, schema=schema)

    # ------------------------------------------------------------------
    # Cross-cutting — entity-set resolution for agent overrides
    # ------------------------------------------------------------------

    @traced(name="resolve_entity_set", run_type="uipath")
    def resolve_entity_set(
        self,
        items: List[DataFabricEntityItem],
    ) -> EntitySetResolution:
        """Resolve an agent entity set, applying resource overwrites."""
        plan = create_resolution_plan(
            items,
            _resource_overwrites.get() or {},
            lambda folder_path: (
                self._folders_service.retrieve_key(folder_path=folder_path)
                if self._folders_service is not None
                else None
            ),
        )
        entities = fetch_resolved_entities(
            plan,
            self.retrieve,
            self.retrieve_by_name,
            logger,
        )
        resolution_service: EntitiesService = build_resolution_service(  # type: ignore[assignment]
            config=self._config,
            execution_context=self._execution_context,
            folders_service=self._folders_service,
            plan=plan,
            service_factory=EntitiesService,
        )
        return EntitySetResolution(
            entities=entities,
            entities_service=resolution_service,
        )

    @traced(name="resolve_entity_set", run_type="uipath")
    async def resolve_entity_set_async(
        self,
        items: List[DataFabricEntityItem],
    ) -> EntitySetResolution:
        """Resolve an agent entity set, applying resource overwrites."""

        async def _resolve_folder_path(folder_path: str) -> Optional[str]:
            if self._folders_service is None:
                return None
            return await self._folders_service.retrieve_key_async(
                folder_path=folder_path
            )

        plan = await create_resolution_plan_async(
            items,
            _resource_overwrites.get() or {},
            _resolve_folder_path,
        )
        entities = await fetch_resolved_entities_async(
            plan,
            self.retrieve_async,
            self.retrieve_by_name_async,
            logger,
        )
        resolution_service: EntitiesService = build_resolution_service(  # type: ignore[assignment]
            config=self._config,
            execution_context=self._execution_context,
            folders_service=self._folders_service,
            plan=plan,
            service_factory=EntitiesService,
        )
        return EntitySetResolution(
            entities=entities,
            entities_service=resolution_service,
        )


# Resolve the forward reference to EntitiesService in EntitySetResolution.
# The model uses TYPE_CHECKING to avoid circular imports in entities.py,
# so we must rebuild it here where EntitiesService is fully defined.
EntitySetResolution.model_rebuild()
