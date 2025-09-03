import json
from typing import List, Optional, Type, TypeVar

from httpx import Response
from pydantic import BaseModel

from .._config import Config
from .._execution_context import ExecutionContext
from .._utils import Endpoint, RequestSpec
from ..models.entities import (
    EntityGetByIdResponse,
    EntityRecord,
    EntityRecordsBatchResponse,
)
from ..tracing import traced
from ._base_service import BaseService

T = TypeVar("T", bound=BaseModel)


class EntitiesService(BaseService):
    def __init__(self, config: Config, execution_context: ExecutionContext) -> None:
        super().__init__(config=config, execution_context=execution_context)

    @traced(name="entity_retrieve", run_type="uipath")
    def retrieve(self, entity_key: str) -> EntityGetByIdResponse:
        spec = self._retrieve_spec(entity_key)
        response = self.request(spec.method, spec.endpoint)

        return EntityGetByIdResponse.model_validate(response.json())

    @traced(name="entity_retrieve", run_type="uipath")
    async def retrieve_async(self, entity_key: str) -> EntityGetByIdResponse:
        spec = self._retrieve_spec(entity_key)

        response = await self.request_async(spec.method, spec.endpoint)

        return EntityGetByIdResponse.model_validate(response.json())

    @traced(name="entity_list_records", run_type="uipath")
    def list_records(
        self,
        entity_key: str,
        schema: Optional[Type[T]] = None,  # Optional schema
        start: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[EntityRecord]:
        # Example method to generate the API request specification (mocked here)
        spec = self._list_records_spec(entity_key, start, limit)

        # Make the HTTP request (assumes self.request exists)
        response = self.request(spec.method, spec.endpoint, params=spec.params)

        # Parse the response JSON and extract the "value" field
        records_data = response.json().get("value", [])

        # Validate and wrap records
        validated_records = []
        for record in records_data:
            try:
                # Validate & wrap the record using EntityRecord.from_data
                validated_record = EntityRecord.from_data(data=record, model=schema)
                validated_records.append(validated_record)
            except ValueError as e:
                print(f"Failed to validate record: {record} => {e}")
                continue

        return validated_records

    @traced(name="entity_list_records", run_type="uipath")
    async def list_records_async(
        self,
        entity_key: str,
        schema: Optional[Type[T]] = None,  # Optional schema
        start: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[EntityRecord]:
        spec = self._list_records_spec(entity_key, start, limit)

        # Make the HTTP request (assumes self.request exists)
        response = await self.request_async(
            spec.method, spec.endpoint, params=spec.params
        )

        # Parse the response JSON and extract the "value" field
        records_data = response.json().get("value", [])

        # Validate and wrap records
        validated_records = []
        for record in records_data:
            try:
                # Validate & wrap the record using EntityRecord.from_data
                validated_record = EntityRecord.from_data(data=record, model=schema)
                validated_records.append(validated_record)
            except ValueError as e:
                print(f"Failed to validate record: {record} => {e}")
                continue

        return validated_records

    @traced(name="entity_record_insert_batch", run_type="uipath")
    def insert_records(
        self,
        entity_key: str,
        records: List[T],
        schema: Optional[Type[T]] = None,
    ) -> EntityRecordsBatchResponse:
        spec = self._insert_batch_spec(entity_key, records)
        response = self.request(spec.method, spec.endpoint, content=spec.content)

        return self.validate_entity_batch(response, schema)

    @traced(name="entity_record_insert_batch", run_type="uipath")
    async def insert_records_async(
        self,
        entity_key: str,
        records: List[T],
        schema: Optional[Type[T]] = None,
    ) -> EntityRecordsBatchResponse:
        spec = self._insert_batch_spec(entity_key, records)
        response = await self.request_async(
            spec.method, spec.endpoint, content=spec.content
        )

        return self.validate_entity_batch(response, schema)

    @traced(name="entity_record_update_batch", run_type="uipath")
    def update_records(
        self,
        entity_key: str,
        records: List[T],
        schema: Optional[Type[T]] = None,
    ) -> EntityRecordsBatchResponse:
        valid_records = [
            EntityRecord.from_data(data=record.model_dump(by_alias=True), model=schema)
            for record in records
        ]

        spec = self._update_batch_spec(entity_key, valid_records)
        response = self.request(spec.method, spec.endpoint, content=spec.content)

        return self.validate_entity_batch(response, schema)

    @traced(name="entity_record_update_batch", run_type="uipath")
    async def update_records_async(
        self,
        entity_key: str,
        records: List[T],
        schema: Optional[Type[T]] = None,
    ) -> EntityRecordsBatchResponse:
        valid_records = [
            EntityRecord.from_data(data=record.model_dump(by_alias=True), model=schema)
            for record in records
        ]

        spec = self._update_batch_spec(entity_key, valid_records)
        response = await self.request_async(
            spec.method, spec.endpoint, content=spec.content
        )

        return self.validate_entity_batch(response, schema)

    @traced(name="entity_record_delete_batch", run_type="uipath")
    def delete_records(
        self,
        entity_key: str,
        record_ids: List[str],
    ) -> EntityRecordsBatchResponse:
        spec = self._delete_batch_spec(entity_key, record_ids)
        response = self.request(spec.method, spec.endpoint, content=spec.content)

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
        spec = self._delete_batch_spec(entity_key, record_ids)
        response = await self.request_async(
            spec.method, spec.endpoint, content=spec.content
        )

        delete_records_response = EntityRecordsBatchResponse.model_validate(
            response.json()
        )

        return delete_records_response

    def validate_entity_batch(
        self,
        batch_response: Response,
        schema: Optional[Type[T]] = None,
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

    def _insert_batch_spec(self, entity_key: str, records: List[T]) -> RequestSpec:
        return RequestSpec(
            method="POST",
            endpoint=Endpoint(
                f"datafabric_/api/EntityService/entity/{entity_key}/insert-batch"
            ),
            content=json.dumps([record.__dict__ for record in records]),
        )

    def _update_batch_spec(
        self, entity_key: str, records: List[EntityRecord]
    ) -> RequestSpec:
        return RequestSpec(
            method="POST",
            endpoint=Endpoint(
                f"datafabric_/api/EntityService/entity/{entity_key}/update-batch"
            ),
            content=json.dumps(
                [record.model_dump(by_alias=True) for record in records]
            ),
        )

    def _delete_batch_spec(self, entity_key: str, record_ids: List[str]) -> RequestSpec:
        return RequestSpec(
            method="POST",
            endpoint=Endpoint(
                f"datafabric_/api/EntityService/entity/{entity_key}/delete-batch"
            ),
            content=json.dumps([record for record in record_ids]),
        )
