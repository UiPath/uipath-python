import uuid
from dataclasses import make_dataclass
from typing import Optional
import re
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_httpx import HTTPXMock

from uipath.platform import UiPathApiConfig, UiPathExecutionContext
from uipath.platform.entities import Entity
from uipath.platform.entities._entities_service import EntitiesService


@pytest.fixture
def service(
    config: UiPathApiConfig,
    execution_context: UiPathExecutionContext,
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
    field_type = Optional[int] | None if is_optional else int
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

    @pytest.mark.parametrize(
        "sql_query",
        [
            "SELECT id FROM Customers WHERE id = 1",
            "SELECT id, name FROM Customers LIMIT 10",
            "SELECT * FROM Customers WHERE status = 'Active'",
            "SELECT id, name, email, phone FROM Customers LIMIT 5",
            "SELECT DISTINCT id FROM Customers WHERE id > 100",
        ],
    )
    def test_validate_sql_query_allows_supported_select_queries(
        self,
        sql_query: str, service: EntitiesService
    ) -> None:
        service._validate_sql_query(sql_query)


    @pytest.mark.parametrize(
        "sql_query,error_message",
        [
            ("", "SQL query cannot be empty."),
            ("   ", "SQL query cannot be empty."),
            ("SELECT id FROM Customers; SELECT id FROM Orders", "Only a single SELECT statement is allowed."),
            ("INSERT INTO Customers VALUES (1)", "Only SELECT statements are allowed."),
            (
                "WITH cte AS (SELECT id FROM Customers) SELECT id FROM cte",
                "SQL construct 'WITH' is not allowed in entity queries.",
            ),
            ("SELECT id FROM Customers UNION SELECT id FROM Orders", "SQL construct 'UNION' is not allowed in entity queries."),
            ("SELECT id, SUM(amount) OVER (PARTITION BY id) FROM Orders LIMIT 10", "SQL construct 'OVER' is not allowed in entity queries."),
            ("SELECT id FROM (SELECT id FROM Customers) c", "Subqueries are not allowed."),
            ("SELECT id FROM Customers", "Queries without WHERE must include a LIMIT clause."),
            ("SELECT * FROM Customers LIMIT 10", "SELECT * without filtering is not allowed."),
            (
                "SELECT id, name, email, phone, address FROM Customers LIMIT 10",
                "Selecting more than 4 columns without filtering is not allowed.",
            ),
        ],
    )
    def test_validate_sql_query_rejects_disallowed_queries(
        self,
        sql_query: str, error_message: str, service: EntitiesService
    ) -> None:
        with pytest.raises(ValueError, match=re.escape(error_message)):
            service._validate_sql_query(sql_query)


    def test_query_multiple_entities_rejects_invalid_sql_before_network_call(
        self,
        service: EntitiesService,
    ) -> None:
        service.request = MagicMock()  # type: ignore[method-assign]

        with pytest.raises(
            ValueError, match=re.escape("Only SELECT statements are allowed.")
        ):
            service.query_multiple_entities("UPDATE Customers SET name = 'X'")

        service.request.assert_not_called()  # type: ignore[attr-defined]


    def test_query_multiple_entities_calls_request_for_valid_sql(
        self,
        service: EntitiesService,
    ) -> None:
        response = MagicMock()
        response.json.return_value = {"results": [{"id": 1}, {"id": 2}]}

        service.request = MagicMock(return_value=response)  # type: ignore[method-assign]

        result = service.query_multiple_entities("SELECT id FROM Customers WHERE id > 0")

        assert result == [{"id": 1}, {"id": 2}]
        service.request.assert_called_once()  # type: ignore[attr-defined]


    @pytest.mark.anyio
    async def test_query_multiple_entities_async_rejects_invalid_sql_before_network_call(
        self,
        service: EntitiesService,
    ) -> None:
        service.request_async = AsyncMock()  # type: ignore[method-assign]

        with pytest.raises(ValueError, match=re.escape("Subqueries are not allowed.")):
            await service.query_multiple_entities_async(
                "SELECT id FROM Customers WHERE id IN (SELECT id FROM Orders)"
            )

        service.request_async.assert_not_called()  # type: ignore[attr-defined]


    @pytest.mark.anyio
    async def test_query_multiple_entities_async_calls_request_for_valid_sql(
        self,
        service: EntitiesService,
    ) -> None:
        response = MagicMock()
        response.json.return_value = {"results": [{"id": "c1"}]}

        service.request_async = AsyncMock(return_value=response)  # type: ignore[method-assign]

        result = await service.query_multiple_entities_async(
            "SELECT id FROM Customers WHERE id = 'c1'"
        )

        assert result == [{"id": "c1"}]
        service.request_async.assert_called_once()  # type: ignore[attr-defined]
