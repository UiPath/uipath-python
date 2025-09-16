from typing import Any, List, Optional, Type

from httpx import Response

from .._config import Config
from .._execution_context import ExecutionContext
from .._utils import Endpoint, RequestSpec
from ..models.entities import (
    Entity,
    EntityRecord,
    EntityRecordsBatchResponse,
)
from ..tracing import traced
from ._base_service import BaseService


class EntitiesService(BaseService):
    """Service for managing UiPath Data Service entities.

    Entities are database tables in UiPath Data Service that can store
    structured data for automation processes.
    """

    def __init__(self, config: Config, execution_context: ExecutionContext) -> None:
        super().__init__(config=config, execution_context=execution_context)

    @traced(name="entity_retrieve", run_type="uipath")
    def retrieve(self, entity_key: str) -> Entity:
        """Retrieve an entity by its key.

        Args:
            entity_key (str): The unique key/identifier of the entity.

        Returns:
            Entity: The entity with all its metadata and field definitions.
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
            Entity: The entity with all its metadata and field definitions.
        """
        spec = self._retrieve_spec(entity_key)

        response = await self.request_async(spec.method, spec.endpoint)

        return Entity.model_validate(response.json())

    @traced(name="list_entities", run_type="uipath")
    def list_entities(self) -> List[Entity]:
        """List all entities in the Data Service.

        Returns:
            List[Entity]: A list of all entities with their metadata and field definitions.
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

        Args:
            entity_key (str): The unique key/identifier of the entity.
            schema (Optional[Type[Any]]): Optional schema class for additional validation of records.
            start (Optional[int]): Starting index for pagination.
            limit (Optional[int]): Maximum number of records to return.

        Returns:
            List[EntityRecord]: A list of entity records.
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

        Args:
            entity_key (str): The unique key/identifier of the entity.
            schema (Optional[Type[Any]]): Optional schema class for additional validation of records.
            start (Optional[int]): Starting index for pagination.
            limit (Optional[int]): Maximum number of records to return.

        Returns:
            List[EntityRecord]: A list of entity records.
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
            records (List[Any]): List of records to insert.
            schema (Optional[Type[Any]]): Optional schema class for validation of records.

        Returns:
            EntityRecordsBatchResponse: Response containing successful and failed record operations.
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
            records (List[Any]): List of records to insert.
            schema (Optional[Type[Any]]): Optional schema class for validation of records.

        Returns:
            EntityRecordsBatchResponse: Response containing successful and failed record operations.
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
            records (List[Any]): List of records to update.
            schema (Optional[Type[Any]]): Optional schema class for validation of records.

        Returns:
            EntityRecordsBatchResponse: Response containing successful and failed record operations.
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
            records (List[Any]): List of records to update.
            schema (Optional[Type[Any]]): Optional schema class for validation of records.

        Returns:
            EntityRecordsBatchResponse: Response containing successful and failed record operations.
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
            record_ids (List[str]): List of record IDs to delete.

        Returns:
            EntityRecordsBatchResponse: Response containing successful and failed record operations.
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
            record_ids (List[str]): List of record IDs to delete.

        Returns:
            EntityRecordsBatchResponse: Response containing successful and failed record operations.
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
