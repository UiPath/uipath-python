import json
import re
import uuid
from dataclasses import make_dataclass
from typing import Optional
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_httpx import HTTPXMock

from uipath.platform import UiPathApiConfig, UiPathExecutionContext
from uipath.platform.common._bindings import (
    EntityResourceOverwrite,
    _resource_overwrites,
)
from uipath.platform.entities import ChoiceSetValue, DataFabricEntityItem, Entity
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

    def test_retrieve_records_without_start_and_limit(
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
            url=f"{base_url}{org}{tenant}/datafabric_/api/EntityService/entity/{str(entity_key)}/read",
            status_code=200,
            json={
                "totalCount": 1,
                "value": [
                    {"Id": "12345", "name": "record_name", "integer_field": 10},
                ],
            },
        )

        records = service.list_records(entity_key=str(entity_key))

        sent_request = httpx_mock.get_request()
        if sent_request is None:
            raise Exception("No request was sent")

        # Verify no start or limit query params are sent
        assert "start" not in str(sent_request.url.params)
        assert "limit" not in str(sent_request.url.params)

        assert isinstance(records, list)
        assert len(records) == 1
        assert records[0].id == "12345"

    @pytest.mark.parametrize(
        "sql_query",
        [
            "SELECT id FROM Customers WHERE id = 1",
            "SELECT id, name FROM Customers LIMIT 10",
            "SELECT COUNT(id) FROM Customers",
            "SELECT SUM(amount) FROM Orders",
            "SELECT AVG(price) FROM Products",
            "SELECT MIN(created), MAX(created) FROM Events",
            "SELECT COUNT(id), name FROM Customers LIMIT 10",
            "SELECT id, name, email, phone FROM Customers LIMIT 5",
            "SELECT DISTINCT id FROM Customers WHERE id > 100",
            "SELECT id FROM Customers WHERE name = 'foo;bar'",
            "SELECT id FROM Customers WHERE id = 1;",
            "SELECT id FROM Customers WHERE name = 'DELETE'",
            "SELECT id FROM Customers WHERE status = 'UPDATE me'",
        ],
    )
    def test_validate_sql_query_allows_supported_select_queries(
        self, sql_query: str, service: EntitiesService
    ) -> None:
        service._validate_sql_query(sql_query)

    @pytest.mark.parametrize(
        "sql_query,error_message",
        [
            ("", "SQL query cannot be empty."),
            ("   ", "SQL query cannot be empty."),
            (
                "SELECT id FROM Customers; SELECT id FROM Orders",
                "Only a single SELECT statement is allowed.",
            ),
            ("INSERT INTO Customers VALUES (1)", "Only SELECT statements are allowed."),
            (
                "WITH cte AS (SELECT id FROM Customers) SELECT id FROM cte",
                "SQL construct 'WITH' is not allowed in entity queries.",
            ),
            (
                "SELECT id FROM Customers UNION SELECT id FROM Orders",
                "SQL construct 'UNION' is not allowed in entity queries.",
            ),
            (
                "SELECT id, SUM(amount) OVER (PARTITION BY id) FROM Orders LIMIT 10",
                "SQL construct 'OVER' is not allowed in entity queries.",
            ),
            (
                "SELECT id FROM (SELECT id FROM Customers) c",
                "Subqueries are not allowed.",
            ),
            (
                "SELECT COALESCE((SELECT max(id) FROM Orders), 0) FROM Customers WHERE id = 1",
                "Subqueries are not allowed.",
            ),
            (
                "SELECT id FROM Customers",
                "Queries without WHERE must include a LIMIT clause.",
            ),
            (
                "SELECT UPPER(name) FROM Customers",
                "Queries without WHERE must include a LIMIT clause.",
            ),
            (
                "SELECT COALESCE(name, 'N/A') FROM Customers",
                "Queries without WHERE must include a LIMIT clause.",
            ),
            (
                "SELECT 1 LIMIT 1",
                "Queries must include a FROM clause.",
            ),
            (
                "SELECT COUNT(*) FROM Customers",
                "COUNT(*) is not supported. Use COUNT(column_name) instead.",
            ),
            (
                "SELECT COUNT(*), name FROM Customers LIMIT 10",
                "COUNT(*) is not supported. Use COUNT(column_name) instead.",
            ),
            (
                "SELECT * FROM Customers LIMIT 10",
                "SELECT * is not allowed. Specify column names instead.",
            ),
            (
                "SELECT Customers.* FROM Customers LIMIT 10",
                "SELECT * is not allowed. Specify column names instead.",
            ),
            (
                "SELECT t.* FROM Customers t LIMIT 10",
                "SELECT * is not allowed. Specify column names instead.",
            ),
            (
                "SELECT * FROM Customers WHERE status = 'Active'",
                "SELECT * is not allowed. Specify column names instead.",
            ),
            (
                "SELECT Customers.* FROM Customers WHERE status = 'Active'",
                "SELECT * is not allowed. Specify column names instead.",
            ),
            (
                "SELECT id, name, email, phone, address FROM Customers LIMIT 10",
                "Selecting more than 4 columns without filtering is not allowed.",
            ),
        ],
    )
    def test_validate_sql_query_rejects_disallowed_queries(
        self, sql_query: str, error_message: str, service: EntitiesService
    ) -> None:
        with pytest.raises(ValueError, match=re.escape(error_message)):
            service._validate_sql_query(sql_query)

    def test_query_entity_records_rejects_invalid_sql_before_network_call(
        self,
        service: EntitiesService,
    ) -> None:
        service.request = MagicMock()  # type: ignore[method-assign]

        with pytest.raises(
            ValueError, match=re.escape("Only SELECT statements are allowed.")
        ):
            service.query_entity_records("UPDATE Customers SET name = 'X'")

        service.request.assert_not_called()

    def test_query_entity_records_calls_request_for_valid_sql(
        self,
        service: EntitiesService,
    ) -> None:
        response = MagicMock()
        response.json.return_value = {"results": [{"id": 1}, {"id": 2}]}

        service.request = MagicMock(return_value=response)  # type: ignore[method-assign]

        result = service.query_entity_records("SELECT id FROM Customers WHERE id > 0")

        assert result == [{"id": 1}, {"id": 2}]
        service.request.assert_called_once()

    @pytest.mark.anyio
    async def test_query_entity_records_async_rejects_invalid_sql_before_network_call(
        self,
        service: EntitiesService,
    ) -> None:
        service.request_async = AsyncMock()  # type: ignore[method-assign]

        with pytest.raises(ValueError, match=re.escape("Subqueries are not allowed.")):
            await service.query_entity_records_async(
                "SELECT id FROM Customers WHERE id IN (SELECT id FROM Orders)"
            )

        service.request_async.assert_not_called()

    @pytest.mark.anyio
    async def test_query_entity_records_async_calls_request_for_valid_sql(
        self,
        service: EntitiesService,
    ) -> None:
        response = MagicMock()
        response.json.return_value = {"results": [{"id": "c1"}]}

        service.request_async = AsyncMock(return_value=response)  # type: ignore[method-assign]

        result = await service.query_entity_records_async(
            "SELECT id FROM Customers WHERE id = 'c1'"
        )

        assert result == [{"id": "c1"}]
        service.request_async.assert_called_once()

    def test_query_entity_records_builds_routing_context_from_folders_map(
        self,
        config: UiPathApiConfig,
        execution_context: UiPathExecutionContext,
    ) -> None:
        service = EntitiesService(
            config=config,
            execution_context=execution_context,
            folders_map={"Customers": "solution_folder", "Orders": "folder-2"},
        )
        response = MagicMock()
        response.json.return_value = {"results": [{"id": 1}]}
        service.request = MagicMock(return_value=response)  # type: ignore[method-assign]

        result = service.query_entity_records("SELECT id FROM Customers LIMIT 10")

        assert result == [{"id": 1}]
        call_kwargs = service.request.call_args
        body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert body["query"] == "SELECT id FROM Customers LIMIT 10"
        assert body["routingContext"] == {
            "entityRoutings": [
                {"entityName": "Customers", "folderId": "solution_folder"},
                {"entityName": "Orders", "folderId": "folder-2"},
            ]
        }

    @pytest.mark.anyio
    async def test_query_entity_records_async_builds_routing_context_from_folders_map(
        self,
        config: UiPathApiConfig,
        execution_context: UiPathExecutionContext,
    ) -> None:
        service = EntitiesService(
            config=config,
            execution_context=execution_context,
            folders_map={"Customers": "solution_folder"},
        )
        response = MagicMock()
        response.json.return_value = {"results": [{"id": "c1"}]}
        service.request_async = AsyncMock(return_value=response)  # type: ignore[method-assign]

        result = await service.query_entity_records_async(
            "SELECT id FROM Customers WHERE id = 'c1'"
        )

        assert result == [{"id": "c1"}]
        call_kwargs = service.request_async.call_args
        body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert body["routingContext"] == {
            "entityRoutings": [
                {"entityName": "Customers", "folderId": "solution_folder"},
            ]
        }

    def test_query_entity_records_without_routing_context_omits_key(
        self,
        service: EntitiesService,
    ) -> None:
        response = MagicMock()
        response.json.return_value = {"results": []}
        service.request = MagicMock(return_value=response)  # type: ignore[method-assign]

        service.query_entity_records("SELECT id FROM Customers WHERE id > 0")

        call_kwargs = service.request.call_args
        body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert "routingContext" not in body

    def test_query_entity_records_picks_up_entity_overwrites_from_context(
        self,
        config: UiPathApiConfig,
        execution_context: UiPathExecutionContext,
    ) -> None:
        from uipath.platform.common._bindings import (
            EntityResourceOverwrite,
            _resource_overwrites,
        )

        service = EntitiesService(
            config=config,
            execution_context=execution_context,
        )
        response = MagicMock()
        response.json.return_value = {"results": [{"id": 1}]}
        service.request = MagicMock(return_value=response)  # type: ignore[method-assign]

        overwrite = EntityResourceOverwrite(
            resource_type="entity",
            name="Overwritten Customers",
            folder_id="overwritten-folder-id",
        )
        token = _resource_overwrites.set({"entity.Customers": overwrite})
        try:
            service.query_entity_records("SELECT id FROM Customers LIMIT 10")
        finally:
            _resource_overwrites.reset(token)

        call_kwargs = service.request.call_args
        body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert body["routingContext"] == {
            "entityRoutings": [
                {
                    "entityName": "Customers",
                    "folderId": "overwritten-folder-id",
                    "overrideEntityName": "Overwritten Customers",
                },
            ]
        }

    def test_query_entity_records_merges_folders_map_with_entity_name_overrides(
        self,
        config: UiPathApiConfig,
        execution_context: UiPathExecutionContext,
    ) -> None:
        service = EntitiesService(
            config=config,
            execution_context=execution_context,
            folders_map={
                "Customers": "overwritten-folder-id",
                "Orders": "orders-folder",
            },
            entity_name_overrides={"Customers": "Overwritten Customers"},
        )
        response = MagicMock()
        response.json.return_value = {"results": []}
        service.request = MagicMock(return_value=response)  # type: ignore[method-assign]

        service.query_entity_records("SELECT id FROM Customers LIMIT 10")

        call_kwargs = service.request.call_args
        body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        routings = body["routingContext"]["entityRoutings"]
        assert {
            "entityName": "Customers",
            "folderId": "overwritten-folder-id",
            "overrideEntityName": "Overwritten Customers",
        } in routings
        assert {"entityName": "Orders", "folderId": "orders-folder"} in routings
        # Exactly two routings — no duplicates
        assert len(routings) == 2

    def test_resolve_entity_set_uses_effective_sql_name_in_routing_context(
        self,
        config: UiPathApiConfig,
        execution_context: UiPathExecutionContext,
    ) -> None:
        service = EntitiesService(
            config=config,
            execution_context=execution_context,
        )
        service.retrieve_by_name = MagicMock(  # type: ignore[method-assign]
            return_value=MagicMock(spec=Entity)
        )

        overwrite = EntityResourceOverwrite(
            resource_type="entity",
            name="Overwritten Customers",
            folder_id="known-folder-key",
        )
        token = _resource_overwrites.set({"entity.entity-1": overwrite})
        try:
            resolution = service.resolve_entity_set(
                [
                    DataFabricEntityItem(
                        id="entity-1",
                        name="Customers",
                        folder_key="original-folder-key",
                    )
                ]
            )
        finally:
            _resource_overwrites.reset(token)

        assert resolution.entities_service._routing_strategy.routing_context is not None
        assert resolution.entities_service._routing_strategy.routing_context.model_dump(
            by_alias=True, exclude_none=True
        ) == {
            "entityRoutings": [
                {
                    "entityName": "Customers",
                    "folderId": "known-folder-key",
                    "overrideEntityName": "Overwritten Customers",
                }
            ]
        }
        service.retrieve_by_name.assert_called_once_with(
            "Overwritten Customers",
            "known-folder-key",
        )

    @pytest.mark.asyncio
    async def test_resolve_entity_set_async_resolves_folder_paths_before_fetch(
        self,
        config: UiPathApiConfig,
        execution_context: UiPathExecutionContext,
    ) -> None:
        folders_service = MagicMock()
        folders_service.retrieve_key_async = AsyncMock(
            return_value="resolved-folder-id"
        )
        service = EntitiesService(
            config=config,
            execution_context=execution_context,
            folders_service=folders_service,
        )
        service.retrieve_by_name_async = AsyncMock(  # type: ignore[method-assign]
            return_value=MagicMock(spec=Entity)
        )

        overwrite = EntityResourceOverwrite(
            resource_type="entity",
            name="Overwritten Customers",
            folder_path="Shared/Finance",
        )
        token = _resource_overwrites.set({"entity.entity-1": overwrite})
        try:
            resolution = await service.resolve_entity_set_async(
                [
                    DataFabricEntityItem(
                        id="entity-1",
                        name="Customers",
                        folder_key="original-folder-key",
                    )
                ]
            )
        finally:
            _resource_overwrites.reset(token)

        folders_service.retrieve_key_async.assert_awaited_once_with(
            folder_path="Shared/Finance"
        )
        assert resolution.entities_service._routing_strategy.routing_context is not None
        assert resolution.entities_service._routing_strategy.routing_context.model_dump(
            by_alias=True, exclude_none=True
        ) == {
            "entityRoutings": [
                {
                    "entityName": "Customers",
                    "folderId": "resolved-folder-id",
                    "overrideEntityName": "Overwritten Customers",
                }
            ]
        }
        service.retrieve_by_name_async.assert_awaited_once_with(
            "Overwritten Customers",
            "resolved-folder-id",
        )

    def test_query_entity_records_context_overwrite_same_name_no_override_field(
        self,
        config: UiPathApiConfig,
        execution_context: UiPathExecutionContext,
    ) -> None:
        from uipath.platform.common._bindings import (
            EntityResourceOverwrite,
            _resource_overwrites,
        )

        service = EntitiesService(
            config=config,
            execution_context=execution_context,
        )
        response = MagicMock()
        response.json.return_value = {"results": []}
        service.request = MagicMock(return_value=response)  # type: ignore[method-assign]

        overwrite = EntityResourceOverwrite(
            resource_type="entity",
            name="Customers",
            folder_id="different-folder-id",
        )
        token = _resource_overwrites.set({"entity.Customers": overwrite})
        try:
            service.query_entity_records("SELECT id FROM Customers LIMIT 10")
        finally:
            _resource_overwrites.reset(token)

        call_kwargs = service.request.call_args
        body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert body["routingContext"] == {
            "entityRoutings": [
                {
                    "entityName": "Customers",
                    "folderId": "different-folder-id",
                },
            ]
        }

    def test_query_entity_records_resolves_overwrite_folder_path_to_folder_key(
        self,
        config: UiPathApiConfig,
        execution_context: UiPathExecutionContext,
    ) -> None:
        from uipath.platform.common._bindings import (
            EntityResourceOverwrite,
            _resource_overwrites,
        )

        folders_service = MagicMock()
        folders_service.retrieve_key.return_value = "resolved-folder-id"

        service = EntitiesService(
            config=config,
            execution_context=execution_context,
            folders_service=folders_service,
        )
        response = MagicMock()
        response.json.return_value = {"results": []}
        service.request = MagicMock(return_value=response)  # type: ignore[method-assign]

        overwrite = EntityResourceOverwrite(
            resource_type="entity",
            name="Overwritten Customers",
            folder_path="Shared/Finance",
        )
        token = _resource_overwrites.set({"entity.Customers": overwrite})
        try:
            service.query_entity_records("SELECT id FROM Customers LIMIT 10")
        finally:
            _resource_overwrites.reset(token)

        call_kwargs = service.request.call_args
        body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert body["routingContext"] == {
            "entityRoutings": [
                {
                    "entityName": "Customers",
                    "folderId": "resolved-folder-id",
                    "overrideEntityName": "Overwritten Customers",
                },
            ]
        }

    def test_query_entity_records_uses_folder_id_directly_without_resolution(
        self,
        config: UiPathApiConfig,
        execution_context: UiPathExecutionContext,
    ) -> None:
        from uipath.platform.common._bindings import (
            EntityResourceOverwrite,
            _resource_overwrites,
        )

        folders_service = MagicMock()
        folders_service.retrieve_key.return_value = None

        service = EntitiesService(
            config=config,
            execution_context=execution_context,
            folders_service=folders_service,
        )
        response = MagicMock()
        response.json.return_value = {"results": []}
        service.request = MagicMock(return_value=response)  # type: ignore[method-assign]

        overwrite = EntityResourceOverwrite(
            resource_type="entity",
            name="Overwritten Customers",
            folder_id="known-folder-key",
        )
        token = _resource_overwrites.set({"entity.Customers": overwrite})
        try:
            service.query_entity_records("SELECT id FROM Customers LIMIT 10")
        finally:
            _resource_overwrites.reset(token)

        # folder_id is a key — should NOT be sent through FolderService
        folders_service.retrieve_key.assert_not_called()

        call_kwargs = service.request.call_args
        body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert body["routingContext"] == {
            "entityRoutings": [
                {
                    "entityName": "Customers",
                    "folderId": "known-folder-key",
                    "overrideEntityName": "Overwritten Customers",
                },
            ]
        }

    def test_list_choicesets(
        self,
        httpx_mock: HTTPXMock,
        service: EntitiesService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/datafabric_/api/Entity/choiceset",
            status_code=200,
            json=[
                {
                    "name": "Status",
                    "displayName": "Status",
                    "entityType": "ChoiceSet",
                    "description": "Status choices",
                    "isRbacEnabled": False,
                    "id": "cs-001",
                },
                {
                    "name": "Priority",
                    "displayName": "Priority",
                    "entityType": "ChoiceSet",
                    "description": "Priority levels",
                    "isRbacEnabled": False,
                    "id": "cs-002",
                },
            ],
        )

        choicesets = service.list_choicesets()

        assert isinstance(choicesets, list)
        assert len(choicesets) == 2
        assert choicesets[0].name == "Status"
        assert choicesets[0].entity_type == "ChoiceSet"
        assert choicesets[0].id == "cs-001"
        assert choicesets[1].name == "Priority"

        sent_request = httpx_mock.get_request()
        assert sent_request is not None
        assert sent_request.method == "GET"
        assert str(sent_request.url).endswith("/datafabric_/api/Entity/choiceset")

    @pytest.mark.anyio
    async def test_list_choicesets_async(
        self,
        httpx_mock: HTTPXMock,
        service: EntitiesService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/datafabric_/api/Entity/choiceset",
            status_code=200,
            json=[
                {
                    "name": "Role",
                    "displayName": "Role",
                    "entityType": "ChoiceSet",
                    "isRbacEnabled": False,
                    "id": "cs-003",
                },
            ],
        )

        choicesets = await service.list_choicesets_async()

        assert len(choicesets) == 1
        assert choicesets[0].name == "Role"
        assert choicesets[0].id == "cs-003"

    def test_get_choiceset_values(
        self,
        httpx_mock: HTTPXMock,
        service: EntitiesService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        choiceset_id = "cs-001"
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/datafabric_/api/EntityService/entity/{choiceset_id}/query_expansion",
            status_code=200,
            json={
                "totalRecordCount": 3,
                "jsonValue": json.dumps(
                    [
                        {
                            "Id": "v1",
                            "Name": "Active",
                            "DisplayName": "Active",
                            "NumberId": 0,
                            "CreateTime": "2026-01-01T00:00:00Z",
                            "UpdateTime": "2026-01-01T00:00:00Z",
                        },
                        {
                            "Id": "v2",
                            "Name": "Inactive",
                            "DisplayName": "Inactive",
                            "NumberId": 1,
                            "CreateTime": "2026-01-01T00:00:00Z",
                            "UpdateTime": "2026-01-01T00:00:00Z",
                        },
                        {
                            "Id": "v3",
                            "Name": "Pending",
                            "DisplayName": "Pending",
                            "NumberId": 2,
                        },
                    ]
                ),
            },
        )

        values = service.get_choiceset_values(choiceset_id)

        assert isinstance(values, list)
        assert len(values) == 3
        assert isinstance(values[0], ChoiceSetValue)
        assert values[0].id == "v1"
        assert values[0].name == "Active"
        assert values[0].display_name == "Active"
        assert values[0].number_id == 0
        assert values[1].number_id == 1
        assert values[2].name == "Pending"
        assert values[2].created_by is None

        sent_request = httpx_mock.get_request()
        assert sent_request is not None
        assert sent_request.method == "POST"

    def test_get_choiceset_values_with_pagination(
        self,
        httpx_mock: HTTPXMock,
        service: EntitiesService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        choiceset_id = "cs-001"
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/datafabric_/api/EntityService/entity/{choiceset_id}/query_expansion?start=0&limit=2",
            status_code=200,
            json={
                "totalRecordCount": 5,
                "jsonValue": json.dumps(
                    [
                        {
                            "Id": "v1",
                            "Name": "Active",
                            "DisplayName": "Active",
                            "NumberId": 0,
                        },
                        {
                            "Id": "v2",
                            "Name": "Inactive",
                            "DisplayName": "Inactive",
                            "NumberId": 1,
                        },
                    ]
                ),
            },
        )

        values = service.get_choiceset_values(choiceset_id, start=0, limit=2)

        assert len(values) == 2
        assert values[0].name == "Active"
        assert values[1].name == "Inactive"

        sent_request = httpx_mock.get_request()
        assert sent_request is not None
        assert "start=0" in str(sent_request.url)
        assert "limit=2" in str(sent_request.url)

    @pytest.mark.anyio
    async def test_get_choiceset_values_async(
        self,
        httpx_mock: HTTPXMock,
        service: EntitiesService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        choiceset_id = "cs-002"
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/datafabric_/api/EntityService/entity/{choiceset_id}/query_expansion",
            status_code=200,
            json={
                "totalRecordCount": 1,
                "jsonValue": json.dumps(
                    [
                        {
                            "Id": "v1",
                            "Name": "ReadOnly",
                            "DisplayName": "Read Only",
                            "NumberId": 0,
                        },
                    ]
                ),
            },
        )

        values = await service.get_choiceset_values_async(choiceset_id)

        assert len(values) == 1
        assert values[0].display_name == "Read Only"
        assert values[0].number_id == 0

    def test_get_choiceset_values_empty(
        self,
        httpx_mock: HTTPXMock,
        service: EntitiesService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        choiceset_id = "cs-empty"
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/datafabric_/api/EntityService/entity/{choiceset_id}/query_expansion",
            status_code=200,
            json={
                "totalRecordCount": 0,
                "jsonValue": "[]",
            },
        )

        values = service.get_choiceset_values(choiceset_id)

        assert values == []
