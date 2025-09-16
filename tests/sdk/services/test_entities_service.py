import uuid
from dataclasses import make_dataclass
from typing import Optional

import pytest
from pytest_httpx import HTTPXMock

from uipath._config import Config
from uipath._execution_context import ExecutionContext
from uipath._services import EntitiesService
from uipath.models.entities import Entity


@pytest.fixture
def service(
    config: Config,
    execution_context: ExecutionContext,
    monkeypatch: pytest.MonkeyPatch,
) -> EntitiesService:
    return EntitiesService(config=config, execution_context=execution_context)


@pytest.fixture(params=[True, False], ids=["correct_schema", "incorrect_schema"])
def record_schema(request):
    is_correct = request.param
    field_type = int if is_correct else str
    schema_name = f"RecordSchema{'Correct' if is_correct else 'Incorrect'}"

    RecordSchema = make_dataclass(
        schema_name, [("name", str), ("integer_field", field_type)]
    )

    return RecordSchema, is_correct


@pytest.fixture(params=[True, False], ids=["optional_field", "required_field"])
def record_schema_optional(request):
    is_optional = request.param
    field_type = Optional[int] if is_optional else int
    schema_name = f"RecordSchema{'Optional' if is_optional else 'Required'}"

    RecordSchemaOptional = make_dataclass(
        schema_name, [("name", str), ("integer_field", field_type)]
    )

    return RecordSchemaOptional, is_optional


class TestEntitiesService:
    def test_retrieve(
        self,
        httpx_mock: HTTPXMock,
        service: EntitiesService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        entity_key = uuid.uuid4()
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/datafabric_/api/Entity/{entity_key}",
            status_code=200,
            json={
                "name": "TestEntity",
                "displayName": "TestEntity",
                "entityType": "TestEntityType",
                "description": "TestEntity Description",
                "fields": [
                    {
                        "id": "12345",
                        "name": "field_name",
                        "isPrimaryKey": True,
                        "isForeignKey": False,
                        "isExternalField": False,
                        "isHiddenField": True,
                        "isUnique": True,
                        "referenceType": "ManyToOne",
                        "sqlType": {"name": "VARCHAR", "LengthLimit": 100},
                        "isRequired": True,
                        "displayName": "Field Display Name",
                        "description": "This is a brief description of the field.",
                        "isSystemField": False,
                        "isAttachment": False,
                        "isRbacEnabled": True,
                    }
                ],
                "isRbacEnabled": False,
                "id": f"{entity_key}",
            },
        )

        entity = service.retrieve(entity_key=str(entity_key))

        assert isinstance(entity, Entity)
        assert entity.id == f"{entity_key}"
        assert entity.name == "TestEntity"
        assert entity.display_name == "TestEntity"
        assert entity.entity_type == "TestEntityType"
        assert entity.description == "TestEntity Description"
        assert entity.fields is not None
        assert entity.fields[0].id == "12345"
        assert entity.fields[0].name == "field_name"
        assert entity.fields[0].is_primary_key
        assert not entity.fields[0].is_foreign_key
        assert entity.fields[0].sql_type.name == "VARCHAR"
        assert entity.fields[0].sql_type.length_limit == 100

        sent_request = httpx_mock.get_request()
        if sent_request is None:
            raise Exception("No request was sent")

        assert sent_request.method == "GET"
        assert (
            sent_request.url
            == f"{base_url}{org}{tenant}/datafabric_/api/Entity/{entity_key}"
        )

    def test_retrieve_records_with_no_schema_succeeds(
        self,
        httpx_mock: HTTPXMock,
        service: EntitiesService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        entity_key = uuid.uuid4()
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/datafabric_/api/EntityService/entity/{str(entity_key)}/read?start=0&limit=1",
            status_code=200,
            json={
                "totalCount": 1,
                "value": [
                    {"Id": "12345", "name": "record_name", "integer_field": 10},
                    {"Id": "12346", "name": "record_name2", "integer_field": 11},
                ],
            },
        )

        records = service.list_records(entity_key=str(entity_key), start=0, limit=1)

        sent_request = httpx_mock.get_request()
        if sent_request is None:
            raise Exception("No request was sent")

        assert isinstance(records, list)
        assert len(records) == 2
        assert records[0].id == "12345"
        assert records[0].name == "record_name"
        assert records[0].integer_field == 10
        assert records[1].id == "12346"
        assert records[1].name == "record_name2"
        assert records[1].integer_field == 11

    def test_retrieve_records_with_schema_succeeds(
        self,
        httpx_mock: HTTPXMock,
        service: EntitiesService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
        record_schema,
    ) -> None:
        entity_key = uuid.uuid4()
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/datafabric_/api/EntityService/entity/{str(entity_key)}/read?start=0&limit=1",
            status_code=200,
            json={
                "totalCount": 1,
                "value": [
                    {"Id": "12345", "name": "record_name", "integer_field": 10},
                    {"Id": "12346", "name": "record_name2", "integer_field": 11},
                ],
            },
        )

        # Define the schema for the record. A wrong schema should make the validation fail
        RecordSchema, is_schema_correct = record_schema

        if is_schema_correct:
            records = service.list_records(
                entity_key=str(entity_key), schema=RecordSchema, start=0, limit=1
            )

            sent_request = httpx_mock.get_request()
            if sent_request is None:
                raise Exception("No request was sent")

            assert isinstance(records, list)
            assert len(records) == 2
            assert records[0].id == "12345"
            assert records[0].name == "record_name"
            assert records[0].integer_field == 10
            assert records[1].id == "12346"
            assert records[1].name == "record_name2"
            assert records[1].integer_field == 11
        else:
            # Validation should fail and raise an exception
            with pytest.raises((ValueError, TypeError)):
                service.list_records(
                    entity_key=str(entity_key), schema=RecordSchema, start=0, limit=1
                )

    # Schema validation should take into account optional fields
    def test_retrieve_records_with_optional_fields(
        self,
        httpx_mock: HTTPXMock,
        service: EntitiesService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
        record_schema_optional,
    ) -> None:
        entity_key = uuid.uuid4()
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/datafabric_/api/EntityService/entity/{str(entity_key)}/read?start=0&limit=1",
            status_code=200,
            json={
                "totalCount": 1,
                "value": [
                    {
                        "Id": "12345",
                        "name": "record_name",
                    },
                    {
                        "Id": "12346",
                        "name": "record_name2",
                    },
                ],
            },
        )

        RecordSchemaOptional, is_field_optional = record_schema_optional

        if is_field_optional:
            records = service.list_records(
                entity_key=str(entity_key),
                schema=RecordSchemaOptional,
                start=0,
                limit=1,
            )

            sent_request = httpx_mock.get_request()
            if sent_request is None:
                raise Exception("No request was sent")

            assert isinstance(records, list)
            assert len(records) == 2
            assert records[0].id == "12345"
            assert records[0].name == "record_name"
            assert records[1].id == "12346"
            assert records[1].name == "record_name2"
        else:
            # Validation should fail and raise an exception for missing required field
            with pytest.raises((ValueError, TypeError)):
                service.list_records(
                    entity_key=str(entity_key),
                    schema=RecordSchemaOptional,
                    start=0,
                    limit=1,
                )
