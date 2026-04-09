import logging
from typing import Any, Dict, List, Optional, Type

import sqlparse
from httpx import Response
from sqlparse.sql import Parenthesis, Where
from sqlparse.tokens import DML, Keyword, Wildcard
from uipath.core.tracing import traced

from ..common._base_service import BaseService
from ..common._bindings import _resource_overwrites
from ..common._config import UiPathApiConfig
from ..common._execution_context import UiPathExecutionContext
from ..common._models import Endpoint, RequestSpec
from ..common.constants import HEADER_FOLDER_KEY
from ..orchestrator._folder_service import FolderService
from ._entity_resolution import (
    RoutingStrategy,
    build_resolution_service,
    create_resolution_plan,
    create_resolution_plan_async,
    create_routing_strategy,
    fetch_resolved_entities,
    fetch_resolved_entities_async,
)
from .entities import (
    DataFabricEntityItem,
    Entity,
    EntityRecord,
    EntityRecordsBatchResponse,
    EntitySetResolution,
    QueryRoutingOverrideContext,
)

logger = logging.getLogger(__name__)

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


class EntitiesService(BaseService):
    """Service for managing UiPath Data Service entities.

    Entities are database tables in UiPath Data Service that can store
    structured data for automation processes.

    See Also:
        https://docs.uipath.com/data-service/automation-cloud/latest/user-guide/introduction

    !!! warning "Preview Feature"
        This function is currently experimental.
        Behavior and parameters are subject to change in future versions.
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
        super().__init__(config=config, execution_context=execution_context)
        self._folders_service = folders_service
        self._routing_strategy: RoutingStrategy = create_routing_strategy(
            folders_map=folders_map,
            effective_entity_names=entity_name_overrides,
            routing_context=routing_context,
            folders_service=folders_service,
        )

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
        spec = self._retrieve_spec(entity_key)
        response = self.request(spec.method, spec.endpoint)

        return Entity.model_validate(response.json())

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
        spec = self._retrieve_spec(entity_key)

        response = await self.request_async(spec.method, spec.endpoint)

        return Entity.model_validate(response.json())

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
        spec = self._retrieve_by_name_spec(entity_name)
        headers = self._folder_key_headers(folder_key)
        response = self.request(spec.method, spec.endpoint, headers=headers)
        return Entity.model_validate(response.json())

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
        spec = self._retrieve_by_name_spec(entity_name)
        headers = self._folder_key_headers(folder_key)
        response = await self.request_async(spec.method, spec.endpoint, headers=headers)
        return Entity.model_validate(response.json())

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
        spec = self._list_entities_spec()
        response = self.request(spec.method, spec.endpoint)

        entities_data = response.json()
        return [Entity.model_validate(entity) for entity in entities_data]

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
        spec = self._list_entities_spec()
        response = await self.request_async(spec.method, spec.endpoint)

        entities_data = response.json()
        return [Entity.model_validate(entity) for entity in entities_data]

    @traced(name="entity_list_records", run_type="uipath")
    def list_records(
        self,
        entity_key: str,
        schema: Optional[Type[Any]] = None,  # Optional schema
        start: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[EntityRecord]:
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

        Returns:
            List[EntityRecord]: A list of entity records. Each record contains an 'id' field
                and all other fields from the entity. Fields can be accessed as attributes
                or dictionary keys on the EntityRecord object.

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
        # Example method to generate the API request specification (mocked here)
        spec = self._list_records_spec(entity_key, start, limit)

        # Make the HTTP request (assumes self.request exists)
        response = self.request(spec.method, spec.endpoint, params=spec.params)

        # Parse the response JSON and extract the "value" field
        records_data = response.json().get("value", [])

        # Validate and wrap records
        return [
            EntityRecord.from_data(data=record, model=schema) for record in records_data
        ]

    @traced(name="entity_list_records", run_type="uipath")
    async def list_records_async(
        self,
        entity_key: str,
        schema: Optional[Type[Any]] = None,  # Optional schema
        start: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[EntityRecord]:
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

        Returns:
            List[EntityRecord]: A list of entity records. Each record contains an 'id' field
                and all other fields from the entity. Fields can be accessed as attributes
                or dictionary keys on the EntityRecord object.

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
        spec = self._list_records_spec(entity_key, start, limit)

        # Make the HTTP request (assumes self.request exists)
        response = await self.request_async(
            spec.method, spec.endpoint, params=spec.params
        )

        # Parse the response JSON and extract the "value" field
        records_data = response.json().get("value", [])

        # Validate and wrap records
        return [
            EntityRecord.from_data(data=record, model=schema) for record in records_data
        ]

    @traced(name="entity_query_records", run_type="uipath")
    def query_entity_records(
        self,
        sql_query: str,
    ) -> List[Dict[str, Any]]:
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
        return self._query_entities_for_records(sql_query)

    @traced(name="entity_query_records", run_type="uipath")
    async def query_entity_records_async(
        self,
        sql_query: str,
    ) -> List[Dict[str, Any]]:
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
        return await self._query_entities_for_records_async(sql_query)

    @traced(name="resolve_entity_set", run_type="uipath")
    def resolve_entity_set(
        self,
        items: list[DataFabricEntityItem],
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
        items: list[DataFabricEntityItem],
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

    def _query_entities_for_records(
        self,
        sql_query: str,
    ) -> List[Dict[str, Any]]:
        self._validate_sql_query(sql_query)
        routing_context = self._routing_strategy.resolve()
        spec = self._query_entity_records_spec(sql_query, routing_context)
        response = self.request(spec.method, spec.endpoint, json=spec.json)
        return response.json().get("results", [])

    async def _query_entities_for_records_async(
        self,
        sql_query: str,
    ) -> List[Dict[str, Any]]:
        self._validate_sql_query(sql_query)
        routing_context = await self._routing_strategy.resolve_async()
        spec = self._query_entity_records_spec(sql_query, routing_context)
        response = await self.request_async(spec.method, spec.endpoint, json=spec.json)
        return response.json().get("results", [])

    @traced(name="entity_record_insert_batch", run_type="uipath")
    def insert_records(
        self,
        entity_key: str,
        records: List[Any],
        schema: Optional[Type[Any]] = None,
    ) -> EntityRecordsBatchResponse:
        """Insert multiple records into an entity in a single batch operation.

        Args:
            entity_key (str): The unique key/identifier of the entity.
            records (List[Any]): List of records to insert. Each record should be an object
                with attributes matching the entity's field names.
            schema (Optional[Type[Any]]): Optional schema class for validation. When provided,
                validates that each record in the response matches the schema structure.

        Returns:
            EntityRecordsBatchResponse: Response containing successful and failed record operations.
                - success_records: List of successfully inserted EntityRecord objects
                - failure_records: List of EntityRecord objects that failed to insert

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
        spec = self._insert_batch_spec(entity_key, records)
        response = self.request(spec.method, spec.endpoint, json=spec.json)

        return self.validate_entity_batch(response, schema)

    @traced(name="entity_record_insert_batch", run_type="uipath")
    async def insert_records_async(
        self,
        entity_key: str,
        records: List[Any],
        schema: Optional[Type[Any]] = None,
    ) -> EntityRecordsBatchResponse:
        """Asynchronously insert multiple records into an entity in a single batch operation.

        Args:
            entity_key (str): The unique key/identifier of the entity.
            records (List[Any]): List of records to insert. Each record should be an object
                with attributes matching the entity's field names.
            schema (Optional[Type[Any]]): Optional schema class for validation. When provided,
                validates that each record in the response matches the schema structure.

        Returns:
            EntityRecordsBatchResponse: Response containing successful and failed record operations.
                - success_records: List of successfully inserted EntityRecord objects
                - failure_records: List of EntityRecord objects that failed to insert

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
        spec = self._insert_batch_spec(entity_key, records)
        response = await self.request_async(spec.method, spec.endpoint, json=spec.json)

        return self.validate_entity_batch(response, schema)

    @traced(name="entity_record_update_batch", run_type="uipath")
    def update_records(
        self,
        entity_key: str,
        records: List[Any],
        schema: Optional[Type[Any]] = None,
    ) -> EntityRecordsBatchResponse:
        """Update multiple records in an entity in a single batch operation.

        Args:
            entity_key (str): The unique key/identifier of the entity.
            records (List[Any]): List of records to update. Each record must have an 'Id' field
                and should be a Pydantic model with `model_dump()` method or similar object.
            schema (Optional[Type[Any]]): Optional schema class for validation. When provided,
                validates that each record in the request and response matches the schema structure.

        Returns:
            EntityRecordsBatchResponse: Response containing successful and failed record operations.
                - success_records: List of successfully updated EntityRecord objects
                - failure_records: List of EntityRecord objects that failed to update

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
        valid_records = [
            EntityRecord.from_data(data=record.model_dump(by_alias=True), model=schema)
            for record in records
        ]

        spec = self._update_batch_spec(entity_key, valid_records)
        response = self.request(spec.method, spec.endpoint, json=spec.json)

        return self.validate_entity_batch(response, schema)

    @traced(name="entity_record_update_batch", run_type="uipath")
    async def update_records_async(
        self,
        entity_key: str,
        records: List[Any],
        schema: Optional[Type[Any]] = None,
    ) -> EntityRecordsBatchResponse:
        """Asynchronously update multiple records in an entity in a single batch operation.

        Args:
            entity_key (str): The unique key/identifier of the entity.
            records (List[Any]): List of records to update. Each record must have an 'Id' field
                and should be a Pydantic model with `model_dump()` method or similar object.
            schema (Optional[Type[Any]]): Optional schema class for validation. When provided,
                validates that each record in the request and response matches the schema structure.

        Returns:
            EntityRecordsBatchResponse: Response containing successful and failed record operations.
                - success_records: List of successfully updated EntityRecord objects
                - failure_records: List of EntityRecord objects that failed to update

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
        valid_records = [
            EntityRecord.from_data(data=record.model_dump(by_alias=True), model=schema)
            for record in records
        ]

        spec = self._update_batch_spec(entity_key, valid_records)
        response = await self.request_async(spec.method, spec.endpoint, json=spec.json)

        return self.validate_entity_batch(response, schema)

    @traced(name="entity_record_delete_batch", run_type="uipath")
    def delete_records(
        self,
        entity_key: str,
        record_ids: List[str],
    ) -> EntityRecordsBatchResponse:
        """Delete multiple records from an entity in a single batch operation.

        Args:
            entity_key (str): The unique key/identifier of the entity.
            record_ids (List[str]): List of record IDs (GUIDs) to delete.

        Returns:
            EntityRecordsBatchResponse: Response containing successful and failed record operations.
                - success_records: List of successfully deleted EntityRecord objects
                - failure_records: List of EntityRecord objects that failed to delete

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
        spec = self._delete_batch_spec(entity_key, record_ids)
        response = self.request(spec.method, spec.endpoint, json=spec.json)

        delete_records_response = EntityRecordsBatchResponse.model_validate(
            response.json()
        )

        return delete_records_response

    @traced(name="entity_record_delete_batch", run_type="uipath")
    async def delete_records_async(
        self,
        entity_key: str,
        record_ids: List[str],
    ) -> EntityRecordsBatchResponse:
        """Asynchronously delete multiple records from an entity in a single batch operation.

        Args:
            entity_key (str): The unique key/identifier of the entity.
            record_ids (List[str]): List of record IDs (GUIDs) to delete.

        Returns:
            EntityRecordsBatchResponse: Response containing successful and failed record operations.
                - success_records: List of successfully deleted EntityRecord objects
                - failure_records: List of EntityRecord objects that failed to delete

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
        spec = self._delete_batch_spec(entity_key, record_ids)
        response = await self.request_async(spec.method, spec.endpoint, json=spec.json)

        delete_records_response = EntityRecordsBatchResponse.model_validate(
            response.json()
        )

        return delete_records_response

    def validate_entity_batch(
        self,
        batch_response: Response,
        schema: Optional[Type[Any]] = None,
    ) -> EntityRecordsBatchResponse:
        # Validate the response format
        insert_records_response = EntityRecordsBatchResponse.model_validate(
            batch_response.json()
        )

        # Validate individual records
        validated_successful_records = [
            EntityRecord.from_data(
                data=successful_record.model_dump(by_alias=True), model=schema
            )
            for successful_record in insert_records_response.success_records
        ]

        validated_failed_records = [
            EntityRecord.from_data(
                data=failed_record.model_dump(by_alias=True), model=schema
            )
            for failed_record in insert_records_response.failure_records
        ]

        return EntityRecordsBatchResponse(
            success_records=validated_successful_records,
            failure_records=validated_failed_records,
        )

    def _retrieve_spec(
        self,
        entity_key: str,
    ) -> RequestSpec:
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(f"datafabric_/api/Entity/{entity_key}"),
        )

    def _retrieve_by_name_spec(
        self,
        entity_name: str,
    ) -> RequestSpec:
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(f"datafabric_/api/Entity/{entity_name}/metadata"),
        )

    @staticmethod
    def _folder_key_headers(folder_key: Optional[str]) -> dict[str, str]:
        if folder_key:
            return {HEADER_FOLDER_KEY: folder_key}
        return {}

    def _list_entities_spec(self) -> RequestSpec:
        return RequestSpec(
            method="GET",
            endpoint=Endpoint("datafabric_/api/Entity"),
        )

    def _list_records_spec(
        self,
        entity_key: str,
        start: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> RequestSpec:
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(
                f"datafabric_/api/EntityService/entity/{entity_key}/read"
            ),
            params=({"start": start, "limit": limit}),
        )

    def _query_entity_records_spec(
        self,
        sql_query: str,
        routing_context: Optional[QueryRoutingOverrideContext] = None,
    ) -> RequestSpec:
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

    def _insert_batch_spec(self, entity_key: str, records: List[Any]) -> RequestSpec:
        return RequestSpec(
            method="POST",
            endpoint=Endpoint(
                f"datafabric_/api/EntityService/entity/{entity_key}/insert-batch"
            ),
            json=[record.__dict__ for record in records],
        )

    def _update_batch_spec(
        self, entity_key: str, records: List[EntityRecord]
    ) -> RequestSpec:
        return RequestSpec(
            method="POST",
            endpoint=Endpoint(
                f"datafabric_/api/EntityService/entity/{entity_key}/update-batch"
            ),
            json=[record.model_dump(by_alias=True) for record in records],
        )

    def _delete_batch_spec(self, entity_key: str, record_ids: List[str]) -> RequestSpec:
        return RequestSpec(
            method="POST",
            endpoint=Endpoint(
                f"datafabric_/api/EntityService/entity/{entity_key}/delete-batch"
            ),
            json=record_ids,
        )

    def _validate_sql_query(self, sql_query: str) -> None:
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
        if not has_where and not has_limit:
            raise ValueError("Queries without WHERE must include a LIMIT clause.")

        projection = self._projection_tokens(stmt)
        has_wildcard = any(t.ttype is Wildcard for t in projection)
        if has_wildcard and not has_where:
            raise ValueError("SELECT * without filtering is not allowed.")
        if not has_where and self._projection_column_count(projection) > 4:
            raise ValueError(
                "Selecting more than 4 columns without filtering is not allowed."
            )

    @staticmethod
    def _has_subquery(stmt: sqlparse.sql.Statement) -> bool:
        """Recursively walk the AST looking for SELECT inside parentheses."""

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
    ) -> list[sqlparse.sql.Token]:
        """Extract tokens between the first SELECT and FROM."""
        tokens: list[sqlparse.sql.Token] = []
        collecting = False
        for token in stmt.flatten():
            if token.ttype is DML and token.normalized == "SELECT":
                collecting = True
                continue
            if token.ttype is Keyword and token.normalized == "FROM":
                break
            if collecting:
                tokens.append(token)
        return tokens

    @staticmethod
    def _projection_column_count(
        projection: list[sqlparse.sql.Token],
    ) -> int:
        text = "".join(t.value for t in projection).strip()
        if not text:
            return 0
        return len([part for part in text.split(",") if part.strip()])


# Resolve the forward reference to EntitiesService in EntitySetResolution.
# The model uses TYPE_CHECKING to avoid circular imports in entities.py,
# so we must rebuild it here where EntitiesService is fully defined.
EntitySetResolution.model_rebuild()
