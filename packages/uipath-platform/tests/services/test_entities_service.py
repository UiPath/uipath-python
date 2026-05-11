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
from uipath.platform.entities._entity_data_service import EntityDataService


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
            "SELECT COUNT(id) AS total, SUM(amount) AS amt FROM Orders",
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
        service._data._validate_sql_query(sql_query)

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
                "SELECT COUNT(*) AS total FROM Customers",
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
            service._data._validate_sql_query(sql_query)

    def test_query_entity_records_rejects_invalid_sql_before_network_call(
        self,
        service: EntitiesService,
    ) -> None:
        service._data.request = MagicMock()  # type: ignore[method-assign]

        with pytest.raises(
            ValueError, match=re.escape("Only SELECT statements are allowed.")
        ):
            service.query_entity_records("UPDATE Customers SET name = 'X'")

        service._data.request.assert_not_called()

    def test_query_entity_records_calls_request_for_valid_sql(
        self,
        service: EntitiesService,
    ) -> None:
        response = MagicMock()
        response.json.return_value = {"results": [{"id": 1}, {"id": 2}]}

        service._data.request = MagicMock(return_value=response)  # type: ignore[method-assign]

        result = service.query_entity_records("SELECT id FROM Customers WHERE id > 0")

        assert result == [{"id": 1}, {"id": 2}]
        service._data.request.assert_called_once()

    @pytest.mark.anyio
    async def test_query_entity_records_async_rejects_invalid_sql_before_network_call(
        self,
        service: EntitiesService,
    ) -> None:
        service._data.request_async = AsyncMock()  # type: ignore[method-assign]

        with pytest.raises(ValueError, match=re.escape("Subqueries are not allowed.")):
            await service.query_entity_records_async(
                "SELECT id FROM Customers WHERE id IN (SELECT id FROM Orders)"
            )

        service._data.request_async.assert_not_called()

    @pytest.mark.anyio
    async def test_query_entity_records_async_calls_request_for_valid_sql(
        self,
        service: EntitiesService,
    ) -> None:
        response = MagicMock()
        response.json.return_value = {"results": [{"id": "c1"}]}

        service._data.request_async = AsyncMock(return_value=response)  # type: ignore[method-assign]

        result = await service.query_entity_records_async(
            "SELECT id FROM Customers WHERE id = 'c1'"
        )

        assert result == [{"id": "c1"}]
        service._data.request_async.assert_called_once()

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
        service._data.request = MagicMock(return_value=response)  # type: ignore[method-assign]

        result = service.query_entity_records("SELECT id FROM Customers LIMIT 10")

        assert result == [{"id": 1}]
        call_kwargs = service._data.request.call_args
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
        service._data.request_async = AsyncMock(return_value=response)  # type: ignore[method-assign]

        result = await service.query_entity_records_async(
            "SELECT id FROM Customers WHERE id = 'c1'"
        )

        assert result == [{"id": "c1"}]
        call_kwargs = service._data.request_async.call_args
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
        service._data.request = MagicMock(return_value=response)  # type: ignore[method-assign]

        service.query_entity_records("SELECT id FROM Customers WHERE id > 0")

        call_kwargs = service._data.request.call_args
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
        service._data.request = MagicMock(return_value=response)  # type: ignore[method-assign]

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

        call_kwargs = service._data.request.call_args
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
        service._data.request = MagicMock(return_value=response)  # type: ignore[method-assign]

        service.query_entity_records("SELECT id FROM Customers LIMIT 10")

        call_kwargs = service._data.request.call_args
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
        service._data.request = MagicMock(return_value=response)  # type: ignore[method-assign]

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

        call_kwargs = service._data.request.call_args
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
        service._data.request = MagicMock(return_value=response)  # type: ignore[method-assign]

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

        call_kwargs = service._data.request.call_args
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
        service._data.request = MagicMock(return_value=response)  # type: ignore[method-assign]

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

        call_kwargs = service._data.request.call_args
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


class TestEntitiesServiceNewMethods:
    """Single-record, structured-query, attachment, schema and bulk-import tests."""

    def test_insert_record_fires_post_with_expansion_level(
        self,
        httpx_mock: HTTPXMock,
        service: EntitiesService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        from uipath.platform.entities import EntityRecord

        entity_key = uuid.uuid4()
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/datafabric_/api/EntityService/entity/{entity_key}/insert?expansionLevel=2",
            status_code=200,
            json={"Id": "rec-1", "name": "alice"},
        )

        record = service.insert_record(
            entity_key=str(entity_key),
            data={"name": "alice"},
            expansion_level=2,
        )

        assert isinstance(record, EntityRecord)
        assert record.id == "rec-1"

        sent = httpx_mock.get_request()
        assert sent is not None
        assert sent.method == "POST"
        assert json.loads(sent.content) == {"name": "alice"}

    async def test_insert_record_async(
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
            url=f"{base_url}{org}{tenant}/datafabric_/api/EntityService/entity/{entity_key}/insert",
            status_code=200,
            json={"Id": "rec-1"},
        )

        record = await service.insert_record_async(
            entity_key=str(entity_key), data={"name": "bob"}
        )
        assert record.id == "rec-1"

    def test_get_record(
        self,
        httpx_mock: HTTPXMock,
        service: EntitiesService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        entity_key = uuid.uuid4()
        record_id = "12345"
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/datafabric_/api/EntityService/entity/{entity_key}/read/{record_id}?expansionLevel=1",
            status_code=200,
            json={"Id": record_id, "name": "found"},
        )

        record = service.get_record(
            entity_key=str(entity_key), record_id=record_id, expansion_level=1
        )

        assert record.id == record_id

    def test_update_record_accepts_dict(
        self,
        httpx_mock: HTTPXMock,
        service: EntitiesService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        entity_key = uuid.uuid4()
        record_id = "rec-9"
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/datafabric_/api/EntityService/entity/{entity_key}/update/{record_id}",
            status_code=200,
            json={"Id": record_id, "name": "updated"},
        )

        record = service.update_record(
            entity_key=str(entity_key),
            record_id=record_id,
            data={"name": "updated"},
        )

        assert record.id == record_id
        sent = httpx_mock.get_request()
        assert sent is not None
        assert json.loads(sent.content) == {"name": "updated"}

    def test_delete_record_uses_http_delete(
        self,
        httpx_mock: HTTPXMock,
        service: EntitiesService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        entity_key = uuid.uuid4()
        record_id = "rec-9"
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/datafabric_/api/EntityService/entity/{entity_key}/delete/{record_id}",
            method="DELETE",
            status_code=200,
        )

        service.delete_record(entity_key=str(entity_key), record_id=record_id)

        sent = httpx_mock.get_request()
        assert sent is not None
        assert sent.method == "DELETE"

    def test_query_v1_with_filter_and_pagination(
        self,
        httpx_mock: HTTPXMock,
        service: EntitiesService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        from uipath.platform.entities import (
            EntityQueryFilter,
            EntityQueryFilterGroup,
            EntityQuerySortOption,
            LogicalOperator,
            QueryFilterOperator,
        )

        entity_key = uuid.uuid4()
        httpx_mock.add_response(
            url=re.compile(
                rf"{base_url}{org}{tenant}/datafabric_/api/EntityService/entity/{entity_key}/query.*"
            ),
            status_code=200,
            json={
                "value": [{"Id": "1", "name": "alice"}, {"Id": "2", "name": "bob"}],
                "totalRecordCount": 5,
            },
        )

        result = service.query(
            entity_key=str(entity_key),
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
            sort_options=[EntityQuerySortOption(field_name="name", is_descending=True)],
            selected_fields=["Id", "name"],
            start=0,
            limit=2,
            expansion_level=1,
        )

        assert result.total_count == 5
        assert len(result.items) == 2
        assert result.has_next_page is True
        # Backend doesn't return next_cursor on this endpoint — caller paginates
        # by passing the next ``start`` themselves.
        assert result.next_cursor is None

        sent = httpx_mock.get_request()
        assert sent is not None
        assert "/query" in str(sent.url) and "/v2/" not in str(sent.url)
        # expansionLevel is a URL query param, not body
        assert sent.url.params.get("expansionLevel") == "1"
        body = json.loads(sent.content)
        assert body["filterGroup"]["logicalOperator"] == 0  # And
        assert body["filterGroup"]["queryFilters"][0]["fieldName"] == "status"
        assert body["sortOptions"][0]["fieldName"] == "name"
        assert body["selectedFields"] == ["Id", "name"]
        # start/limit go in BODY, not as $top/$skip query params
        assert body["start"] == 0
        assert body["limit"] == 2

    def test_query_aggregate_response_handles_id_less_rows(
        self,
        httpx_mock: HTTPXMock,
        service: EntitiesService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        """Aggregate / GROUP BY rows lack ``Id`` — must not raise."""
        from uipath.platform.entities import (
            EntityAggregate,
            EntityAggregateFunction,
        )

        entity_key = uuid.uuid4()
        httpx_mock.add_response(
            url=re.compile(
                rf"{base_url}{org}{tenant}/datafabric_/api/EntityService/entity/{entity_key}/query.*"
            ),
            status_code=200,
            json={
                "value": [
                    {"status": "active", "total": 12},
                    {"status": "inactive", "total": 7},
                ],
                "totalRecordCount": 2,
            },
        )

        result = service.query(
            entity_key=str(entity_key),
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

        assert result.total_count == 2
        assert len(result.items) == 2
        # Aggregate rows are exposed as EntityRecord with extra fields, no Id.
        sent = httpx_mock.get_request()
        assert sent is not None
        body = json.loads(sent.content)
        assert body["aggregates"][0]["function"] == "COUNT"
        assert body["aggregates"][0]["alias"] == "total"
        assert body["groupBy"] == ["status"]

    def test_query_v2_when_binnings_provided(
        self,
        httpx_mock: HTTPXMock,
        service: EntitiesService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        from uipath.platform.entities import EntityAggregateFunction, EntityBinning

        entity_key = uuid.uuid4()
        httpx_mock.add_response(
            url=re.compile(
                rf"{base_url}{org}{tenant}/datafabric_/api/v2/EntityService/entity/{entity_key}/query.*"
            ),
            status_code=200,
            json={"value": [], "totalCount": 0},
        )

        service.query(
            entity_key=str(entity_key),
            binnings=[
                EntityBinning(
                    field_name="status",
                    aggregate_function=EntityAggregateFunction.Count,
                    alias="total",
                )
            ],
        )

        sent = httpx_mock.get_request()
        assert sent is not None
        assert "/v2/EntityService/" in str(sent.url)

    def test_upload_attachment_sends_multipart(
        self,
        httpx_mock: HTTPXMock,
        service: EntitiesService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        entity_id = "ent-1"
        record_id = "rec-1"
        field_name = "doc"
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/datafabric_/api/Attachment/entity/{entity_id}/{record_id}/{field_name}?expansionLevel=1",
            method="POST",
            status_code=200,
            json={"Id": record_id, "doc": "uploaded"},
        )

        result = service.upload_attachment(
            entity_id=entity_id,
            record_id=record_id,
            field_name=field_name,
            file=b"hello world",
            expansion_level=1,
        )

        assert result.get("doc") == "uploaded"

        sent = httpx_mock.get_request()
        assert sent is not None
        assert b"hello world" in sent.content

    def test_download_attachment_returns_bytes(
        self,
        httpx_mock: HTTPXMock,
        service: EntitiesService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        entity_id = "ent-1"
        record_id = "rec-1"
        field_name = "doc"
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/datafabric_/api/Attachment/entity/{entity_id}/{record_id}/{field_name}",
            method="GET",
            status_code=200,
            content=b"file-content",
        )

        content = service.download_attachment(
            entity_id=entity_id, record_id=record_id, field_name=field_name
        )
        assert content == b"file-content"

    def test_delete_attachment(
        self,
        httpx_mock: HTTPXMock,
        service: EntitiesService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        entity_id = "ent-1"
        record_id = "rec-1"
        field_name = "doc"
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/datafabric_/api/Attachment/entity/{entity_id}/{record_id}/{field_name}",
            method="DELETE",
            status_code=200,
            json={},
        )

        result = service.delete_attachment(
            entity_id=entity_id, record_id=record_id, field_name=field_name
        )
        assert result == {}

    def test_create_entity_returns_id(
        self,
        httpx_mock: HTTPXMock,
        service: EntitiesService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        from uipath.platform.entities import (
            EntityCreateFieldOptions,
            EntityCreateOptions,
            EntityFieldDataType,
        )

        new_entity_id = str(uuid.uuid4())
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/datafabric_/api/Entity",
            method="POST",
            status_code=200,
            json=new_entity_id,
        )

        created_id = service.create_entity(
            name="productCatalog",
            fields=[
                EntityCreateFieldOptions(
                    field_name="productName",
                    type=EntityFieldDataType.STRING,
                    is_required=True,
                    length_limit=200,
                ),
            ],
            options=EntityCreateOptions(
                display_name="Product Catalog",
                description="Catalog of products",
                is_rbac_enabled=True,
            ),
        )

        assert created_id == new_entity_id
        sent = httpx_mock.get_request()
        assert sent is not None
        body = json.loads(sent.content)
        assert body["displayName"] == "Product Catalog"
        assert body["entityDefinition"]["name"] == "productCatalog"
        assert body["entityDefinition"]["fields"][0]["name"] == "productName"
        assert body["entityDefinition"]["isRbacEnabled"] is True

    def test_delete_entity(
        self,
        httpx_mock: HTTPXMock,
        service: EntitiesService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        entity_id = "ent-doomed"
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/datafabric_/api/Entity/{entity_id}",
            method="DELETE",
            status_code=200,
        )

        service.delete_entity(entity_id=entity_id)
        sent = httpx_mock.get_request()
        assert sent is not None
        assert sent.method == "DELETE"

    def test_update_entity_metadata(
        self,
        httpx_mock: HTTPXMock,
        service: EntitiesService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        from uipath.platform.entities import EntityMetadataUpdateOptions

        entity_id = "ent-meta"
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/datafabric_/api/Entity/{entity_id}/metadata",
            method="PATCH",
            status_code=200,
            json={},
        )

        service.update_entity_metadata(
            entity_id=entity_id,
            metadata=EntityMetadataUpdateOptions(
                display_name="New Name", is_rbac_enabled=False
            ),
        )

        sent = httpx_mock.get_request()
        assert sent is not None
        body = json.loads(sent.content)
        assert body == {"displayName": "New Name", "isRbacEnabled": False}

    def test_import_records(
        self,
        httpx_mock: HTTPXMock,
        service: EntitiesService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        entity_id = "ent-imp"
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/datafabric_/api/EntityService/entity/{entity_id}/bulk-upload",
            method="POST",
            status_code=200,
            json={
                "totalRecords": 10,
                "insertedRecords": 9,
                "errorFileLink": "https://example.com/errors.csv",
            },
        )

        result = service.import_records(entity_id=entity_id, file=b"a,b,c\n1,2,3\n")
        assert result.total_records == 10
        assert result.inserted_records == 9
        assert result.error_file_link == "https://example.com/errors.csv"

    def test_list_records_returns_paginated_metadata(
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
            url=re.compile(
                rf"{base_url}{org}{tenant}/datafabric_/api/EntityService/entity/{entity_key}/read.*"
            ),
            status_code=200,
            json={
                "totalCount": 7,
                "value": [{"Id": "1"}, {"Id": "2"}, {"Id": "3"}],
            },
        )

        records = service.list_records(
            entity_key=str(entity_key),
            start=0,
            limit=3,
            expansion_level=2,
            filter="status eq 'active'",
            orderby="name asc",
            select=["Id", "name"],
            expand=["Company"],
        )

        # New pagination metadata: backend totalCount surfaced verbatim.
        assert records.total_count == 7
        assert records.has_next_page is True
        # Backend does not currently emit next_cursor; caller paginates with start.
        assert records.next_cursor is None

        # Backward-compat: behaves as a list.
        assert isinstance(records, list)
        assert len(records) == 3
        assert records[0].id == "1"

        sent = httpx_mock.get_request()
        assert sent is not None
        params = sent.url.params
        assert params.get("expansionLevel") == "2"
        assert params.get("$filter") == "status eq 'active'"
        assert params.get("$orderby") == "name asc"
        assert params.get("$select") == "Id,name"
        assert params.get("$expand") == "Company"

    def test_insert_records_passes_expansion_level_and_fail_on_first(
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
            url=re.compile(
                rf"{base_url}{org}{tenant}/datafabric_/api/EntityService/entity/{entity_key}/insert-batch.*"
            ),
            status_code=200,
            json={"successRecords": [{"Id": "1"}], "failureRecords": []},
        )

        service.insert_records(
            entity_key=str(entity_key),
            records=[{"name": "alice"}],
            expansion_level=1,
            fail_on_first=True,
        )

        sent = httpx_mock.get_request()
        assert sent is not None
        params = sent.url.params
        assert params.get("expansionLevel") == "1"
        assert params.get("failOnFirst") == "true"
        # Records are normalized to dicts before being sent.
        assert json.loads(sent.content) == [{"name": "alice"}]

    def test_update_records_recovers_failure_records_from_4xx(
        self,
        httpx_mock: HTTPXMock,
        service: EntitiesService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        """A 400 response that lists per-record failures should parse into the response.

        The caller receives an ``EntityRecordsBatchResponse`` with the failed
        records populated rather than an exception, so unknown record ids on
        update can be handled the same way as any other batch failure.
        """
        entity_key = uuid.uuid4()
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/datafabric_/api/EntityService/entity/{entity_key}/update-batch",
            method="POST",
            status_code=400,
            json={
                "successRecords": [],
                "failureRecords": [
                    {"error": "Record not found", "record": {"Id": "missing"}}
                ],
            },
        )

        result = service.update_records(
            entity_key=str(entity_key),
            records=[{"Id": "missing", "name": "x"}],
        )

        assert len(result.failure_records) == 1
        assert result.failure_records[0].error == "Record not found"

    def test_delete_records_recovers_failure_records_from_4xx(
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
            url=f"{base_url}{org}{tenant}/datafabric_/api/EntityService/entity/{entity_key}/delete-batch",
            method="POST",
            status_code=400,
            json={
                "successRecords": [],
                "failureRecords": [{"error": "not found"}],
            },
        )

        result = service.delete_records(
            entity_key=str(entity_key), record_ids=["missing"]
        )

        assert result.failure_records[0].error == "not found"

    def test_record_to_dict_accepts_dict_pydantic_and_object(self) -> None:
        from uipath.platform.entities import EntityCreateFieldOptions

        # dict
        assert EntityDataService._record_to_dict({"a": 1}) == {"a": 1}
        # Pydantic model — uses model_dump
        result = EntityDataService._record_to_dict(
            EntityCreateFieldOptions(field_name="x")
        )
        assert result["fieldName"] == "x"
        # Object with __dict__
        from dataclasses import dataclass

        @dataclass
        class Rec:
            name: str

        assert EntityDataService._record_to_dict(Rec(name="bob")) == {"name": "bob"}


class TestEntitiesServiceCreateEntitySqlTypeMapping:
    """Verify ``create_entity`` produces the SQL types and constraint defaults the backend expects."""

    def _captured_field(
        self,
        httpx_mock: HTTPXMock,
        service: EntitiesService,
        base_url: str,
        org: str,
        tenant: str,
        field_options,
    ):
        from uipath.platform.entities import EntityCreateOptions

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/datafabric_/api/Entity",
            method="POST",
            status_code=200,
            json="00000000-0000-0000-0000-000000000001",
        )
        service.create_entity(
            name="myEntity",
            fields=[field_options],
            options=EntityCreateOptions(display_name="My Entity"),
        )
        sent = httpx_mock.get_request()
        assert sent is not None
        body = json.loads(sent.content)
        return body["entityDefinition"]["fields"][0]

    def test_string_field_maps_to_nvarchar_with_default_length(
        self, httpx_mock, service, base_url, org, tenant, version
    ) -> None:
        from uipath.platform.entities import (
            EntityCreateFieldOptions,
            EntityFieldDataType,
        )

        f = self._captured_field(
            httpx_mock,
            service,
            base_url,
            org,
            tenant,
            EntityCreateFieldOptions(
                field_name="productName", type=EntityFieldDataType.STRING
            ),
        )
        assert f["sqlType"]["name"] == "NVARCHAR"
        assert f["sqlType"]["lengthLimit"] == 200  # default
        assert f["fieldDisplayType"] == "Basic"

    def test_decimal_field_includes_precision_and_value_bounds(
        self, httpx_mock, service, base_url, org, tenant, version
    ) -> None:
        from uipath.platform.entities import (
            EntityCreateFieldOptions,
            EntityFieldDataType,
        )

        f = self._captured_field(
            httpx_mock,
            service,
            base_url,
            org,
            tenant,
            EntityCreateFieldOptions(
                field_name="price",
                type=EntityFieldDataType.DECIMAL,
                decimal_precision=4,
            ),
        )
        assert f["sqlType"]["name"] == "DECIMAL"
        assert f["sqlType"]["decimalPrecision"] == 4
        assert f["sqlType"]["lengthLimit"] == 1000
        assert f["sqlType"]["maxValue"] == 1_000_000_000_000
        assert f["sqlType"]["minValue"] == -1_000_000_000_000

    def test_boolean_field_maps_to_bit(
        self, httpx_mock, service, base_url, org, tenant, version
    ) -> None:
        from uipath.platform.entities import (
            EntityCreateFieldOptions,
            EntityFieldDataType,
        )

        f = self._captured_field(
            httpx_mock,
            service,
            base_url,
            org,
            tenant,
            EntityCreateFieldOptions(
                field_name="isActive", type=EntityFieldDataType.BOOLEAN
            ),
        )
        assert f["sqlType"]["name"] == "BIT"
        assert f["sqlType"]["lengthLimit"] == 100

    def test_file_field_maps_to_uniqueidentifier_with_file_display_type(
        self, httpx_mock, service, base_url, org, tenant, version
    ) -> None:
        from uipath.platform.entities import (
            EntityCreateFieldOptions,
            EntityFieldDataType,
        )

        f = self._captured_field(
            httpx_mock,
            service,
            base_url,
            org,
            tenant,
            EntityCreateFieldOptions(
                field_name="document", type=EntityFieldDataType.FILE
            ),
        )
        assert f["sqlType"]["name"] == "UNIQUEIDENTIFIER"
        assert f["fieldDisplayType"] == "File"
        assert f["sqlType"]["lengthLimit"] == 300


class TestEntitiesServiceValidation:
    """Client-side validation rejects bad entity / field definitions before any HTTP call."""

    def test_create_entity_rejects_invalid_entity_name(self, service) -> None:

        with pytest.raises(ValueError, match="Invalid entity name"):
            service.create_entity(name="1bad", fields=[])

    def test_create_entity_rejects_invalid_field_name(self, service) -> None:
        from uipath.platform.entities import EntityCreateFieldOptions

        with pytest.raises(ValueError, match="Invalid field name"):
            service.create_entity(
                name="goodEntity",
                fields=[EntityCreateFieldOptions(field_name="9bad")],
            )

    def test_create_entity_rejects_reserved_field_name(self, service) -> None:
        from uipath.platform.entities import EntityCreateFieldOptions

        with pytest.raises(ValueError, match="reserved"):
            service.create_entity(
                name="goodEntity",
                fields=[EntityCreateFieldOptions(field_name="Id")],
            )

    def test_create_entity_rejects_unsupported_constraint_for_type(
        self, service
    ) -> None:
        from uipath.platform.entities import (
            EntityCreateFieldOptions,
            EntityFieldDataType,
        )

        with pytest.raises(ValueError, match="does not accept"):
            service.create_entity(
                name="goodEntity",
                fields=[
                    EntityCreateFieldOptions(
                        field_name="myField",
                        type=EntityFieldDataType.STRING,
                        decimal_precision=2,  # not allowed on STRING
                    )
                ],
            )

    def test_create_entity_rejects_out_of_range_constraint(self, service) -> None:
        from uipath.platform.entities import (
            EntityCreateFieldOptions,
            EntityFieldDataType,
        )

        with pytest.raises(ValueError, match="out of range"):
            service.create_entity(
                name="goodEntity",
                fields=[
                    EntityCreateFieldOptions(
                        field_name="myField",
                        type=EntityFieldDataType.STRING,
                        length_limit=99999,  # > 4000
                    )
                ],
            )

    def test_create_entity_rejects_min_ge_max(self, service) -> None:
        from uipath.platform.entities import (
            EntityCreateFieldOptions,
            EntityFieldDataType,
        )

        with pytest.raises(ValueError, match="strictly less than"):
            service.create_entity(
                name="goodEntity",
                fields=[
                    EntityCreateFieldOptions(
                        field_name="myField",
                        type=EntityFieldDataType.INTEGER,
                        min_value=100,
                        max_value=10,
                    )
                ],
            )


class TestEntitiesServiceAsyncAndEdgeCases:
    async def test_get_record_async(
        self, httpx_mock, service, base_url, org, tenant, version
    ) -> None:
        entity_key = uuid.uuid4()
        record_id = "rec-1"
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/datafabric_/api/EntityService/entity/{entity_key}/read/{record_id}",
            status_code=200,
            json={"Id": record_id, "name": "found"},
        )
        record = await service.get_record_async(
            entity_key=str(entity_key), record_id=record_id
        )
        assert record.id == record_id

    async def test_query_async_v1(
        self, httpx_mock, service, base_url, org, tenant, version
    ) -> None:
        entity_key = uuid.uuid4()
        httpx_mock.add_response(
            url=re.compile(
                rf"{base_url}{org}{tenant}/datafabric_/api/EntityService/entity/{entity_key}/query"
            ),
            status_code=200,
            json={"value": [{"Id": "1"}], "totalRecordCount": 1},
        )
        result = await service.query_async(entity_key=str(entity_key))
        assert result.total_count == 1

    async def test_delete_record_async(
        self, httpx_mock, service, base_url, org, tenant, version
    ) -> None:
        entity_key = uuid.uuid4()
        record_id = "rec-1"
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/datafabric_/api/EntityService/entity/{entity_key}/delete/{record_id}",
            method="DELETE",
            status_code=200,
        )
        await service.delete_record_async(
            entity_key=str(entity_key), record_id=record_id
        )

    async def test_create_entity_async(
        self, httpx_mock, service, base_url, org, tenant, version
    ) -> None:
        from uipath.platform.entities import (
            EntityCreateFieldOptions,
            EntityFieldDataType,
        )

        new_id = "00000000-0000-0000-0000-000000000123"
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/datafabric_/api/Entity",
            method="POST",
            status_code=200,
            json=new_id,
        )
        result = await service.create_entity_async(
            name="goodEntity",
            fields=[
                EntityCreateFieldOptions(
                    field_name="myField", type=EntityFieldDataType.STRING
                )
            ],
        )
        assert result == new_id

    async def test_delete_entity_async(
        self, httpx_mock, service, base_url, org, tenant, version
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/datafabric_/api/Entity/ent-1",
            method="DELETE",
            status_code=200,
        )
        await service.delete_entity_async(entity_id="ent-1")

    async def test_update_entity_metadata_async_with_dict(
        self, httpx_mock, service, base_url, org, tenant, version
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/datafabric_/api/Entity/ent-1/metadata",
            method="PATCH",
            status_code=200,
            json={},
        )
        # Accepts a plain dict too
        await service.update_entity_metadata_async(
            entity_id="ent-1", metadata={"displayName": "X", "description": "Y"}
        )
        sent = httpx_mock.get_request()
        assert sent is not None
        assert json.loads(sent.content) == {"displayName": "X", "description": "Y"}

    def test_update_entity_metadata_normalizes_snake_case_dict_keys(
        self, httpx_mock, service, base_url, org, tenant, version
    ) -> None:
        """Snake_case dict keys must be sent to the backend as camelCase."""
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/datafabric_/api/Entity/ent-1/metadata",
            method="PATCH",
            status_code=200,
            json={},
        )
        service.update_entity_metadata(
            entity_id="ent-1",
            metadata={
                "display_name": "New Name",
                "description": "Updated",
                "is_rbac_enabled": True,
            },
        )
        sent = httpx_mock.get_request()
        assert sent is not None
        assert json.loads(sent.content) == {
            "displayName": "New Name",
            "description": "Updated",
            "isRbacEnabled": True,
        }

    async def test_upload_attachment_async_via_file_path(
        self, httpx_mock, service, base_url, org, tenant, version, tmp_path
    ) -> None:
        path = tmp_path / "data.bin"
        path.write_bytes(b"file-on-disk")

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/datafabric_/api/Attachment/entity/ent/rec/doc",
            method="POST",
            status_code=200,
            json={"Id": "rec", "doc": "ok"},
        )
        result = await service.upload_attachment_async(
            entity_id="ent",
            record_id="rec",
            field_name="doc",
            file_path=str(path),
        )
        assert result["doc"] == "ok"

        sent = httpx_mock.get_request()
        assert sent is not None
        assert b"file-on-disk" in sent.content

    async def test_download_and_delete_attachment_async(
        self, httpx_mock, service, base_url, org, tenant, version
    ) -> None:
        url = f"{base_url}{org}{tenant}/datafabric_/api/Attachment/entity/e/r/f"
        httpx_mock.add_response(
            url=url, method="GET", status_code=200, content=b"bytes"
        )
        httpx_mock.add_response(url=url, method="DELETE", status_code=200, json={})

        content = await service.download_attachment_async(
            entity_id="e", record_id="r", field_name="f"
        )
        assert content == b"bytes"
        assert (
            await service.delete_attachment_async(
                entity_id="e", record_id="r", field_name="f"
            )
            == {}
        )

    def test_open_file_rejects_both_file_and_path(self) -> None:
        with pytest.raises(ValueError, match="exactly one of"):
            EntityDataService._open_file(file=b"x", file_path="some/path")

    def test_open_file_rejects_neither_file_nor_path(self) -> None:
        with pytest.raises(ValueError, match="exactly one of"):
            EntityDataService._open_file(file=None, file_path=None)

    def test_4xx_recovery_only_400_with_strict_shape(
        self, httpx_mock, service, base_url, org, tenant, version
    ) -> None:
        """5xx and 4xx other than 400 must propagate; 400 with valid shape recovers."""
        entity_key = uuid.uuid4()
        # 500 with the shape — must propagate, not be silently treated as success.
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/datafabric_/api/EntityService/entity/{entity_key}/update-batch",
            method="POST",
            status_code=500,
            json={"successRecords": [], "failureRecords": []},
        )
        from uipath.platform.errors._enriched_exception import EnrichedException

        with pytest.raises(EnrichedException):
            service.update_records(
                entity_key=str(entity_key), records=[{"Id": "x", "name": "y"}]
            )

    def test_4xx_recovery_404_propagates(
        self, httpx_mock, service, base_url, org, tenant, version
    ) -> None:
        entity_key = uuid.uuid4()
        # 404 with valid shape — still propagates because not a 400.
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/datafabric_/api/EntityService/entity/{entity_key}/update-batch",
            method="POST",
            status_code=404,
            json={"successRecords": [], "failureRecords": []},
        )
        from uipath.platform.errors._enriched_exception import EnrichedException

        with pytest.raises(EnrichedException):
            service.update_records(
                entity_key=str(entity_key), records=[{"Id": "x", "name": "y"}]
            )

    def test_4xx_recovery_400_unrelated_body_propagates(
        self, httpx_mock, service, base_url, org, tenant, version
    ) -> None:
        """A 400 with an error body that lacks ``successRecords``/``failureRecords``
        must surface as an exception (so generic validation errors aren't masked)."""
        entity_key = uuid.uuid4()
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/datafabric_/api/EntityService/entity/{entity_key}/update-batch",
            method="POST",
            status_code=400,
            json={"error": "Validation failed", "code": "InvalidArg"},
        )
        from uipath.platform.errors._enriched_exception import EnrichedException

        with pytest.raises(EnrichedException):
            service.update_records(
                entity_key=str(entity_key), records=[{"Id": "x", "name": "y"}]
            )
