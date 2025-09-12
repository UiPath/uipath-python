import uuid
from dataclasses import dataclass
from typing import Optional

import pytest
from pytest_httpx import HTTPXMock

from uipath._config import Config
from uipath._execution_context import ExecutionContext
from uipath._services import EntitiesService
from uipath.models.entities import EntityGetByIdResponse


@pytest.fixture
def service(
    config: Config,
    execution_context: ExecutionContext,
    monkeypatch: pytest.MonkeyPatch,
) -> EntitiesService:
    return EntitiesService(config=config, execution_context=execution_context)


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

        assert isinstance(entity, EntityGetByIdResponse)
        assert entity.id == f"{entity_key}"
        assert entity.name == "TestEntity"
        assert entity.display_name == "TestEntity"
        assert entity.entity_type == "TestEntityType"
        assert entity.description == "TestEntity Description"
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

    @pytest.mark.parametrize(
        "is_schema_correct",
        [
            True,
            False,
        ],
    )
    def test_retrieve_records_with_schema_succeeds(
        self,
        httpx_mock: HTTPXMock,
        service: EntitiesService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
        is_schema_correct: bool,
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
        if is_schema_correct:

            @dataclass
            class RecordSchema:
                name: str
                integer_field: int
        else:

            @dataclass
            class RecordSchema:
                name: str
                integer_field: str  # making the field a str instead of int should make the validation fail

        records = service.list_records(
            entity_key=str(entity_key), schema=RecordSchema, start=0, limit=1
        )

        sent_request = httpx_mock.get_request()
        if sent_request is None:
            raise Exception("No request was sent")

        if is_schema_correct:
            assert isinstance(records, list)
            assert len(records) == 2
            assert records[0].id == "12345"
            assert records[0].name == "record_name"
            assert records[0].integer_field == 10
            assert records[1].id == "12346"
            assert records[1].name == "record_name2"
            assert records[1].integer_field == 11
        else:
            assert isinstance(records, list)
            assert (
                len(records) == 0
            )  # no records should have been returned as the validation failed

    # Schema validation should take into account optional fields
    @pytest.mark.parametrize(
        "is_field_optional",
        [
            True,
            False,
        ],
    )
    def test_retrieve_records_with_optional_fields(
        self,
        httpx_mock: HTTPXMock,
        service: EntitiesService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
        is_field_optional: bool,
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

        if is_field_optional:

            @dataclass
            class RecordSchemaOptional:
                name: str
                integer_field: Optional[int]  #
        else:

            @dataclass
            class RecordSchemaOptional:
                name: str
                integer_field: (
                    int  # making the field a required should fail the validation
                )

        records = service.list_records(
            entity_key=str(entity_key), schema=RecordSchemaOptional, start=0, limit=1
        )

        sent_request = httpx_mock.get_request()
        if sent_request is None:
            raise Exception("No request was sent")

        if is_field_optional:
            assert isinstance(records, list)
            assert len(records) == 2
            assert records[0].id == "12345"
            assert records[0].name == "record_name"
            assert records[1].id == "12346"
            assert records[1].name == "record_name2"
        else:
            assert isinstance(records, list)
            assert (
                len(records) == 0
            )  # no records should have been returned as the validation failed
