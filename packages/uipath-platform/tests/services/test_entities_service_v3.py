"""Tests for the experimental v3 EntitiesService methods (``*_v3``).

The v1 methods are covered in ``test_entities_service.py`` and remain on the
legacy ``datafabric_/api/Entity`` / ``EntityService`` surfaces; these tests lock
the parallel ``*_v3`` methods to the ``datafabric_/api/v3/entities`` surface.
"""

import json
import re
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_httpx import HTTPXMock

from uipath.platform import UiPathApiConfig, UiPathExecutionContext
from uipath.platform.common._bindings import (
    EntityResourceOverwrite,
    _resource_overwrites,
)
from uipath.platform.entities import DataFabricEntityItem, Entity
from uipath.platform.entities._entities_service import EntitiesService
from uipath.platform.errors import EnrichedException

TENANT_FOLDER = "00000000-0000-0000-0000-000000000000"


@pytest.fixture
def service(
    config: UiPathApiConfig,
    execution_context: UiPathExecutionContext,
) -> EntitiesService:
    return EntitiesService(config=config, execution_context=execution_context)


class TestEntitiesServiceV3:
    def test_retrieve_v3_hits_v3_surface(
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
            url=f"{base_url}{org}{tenant}/datafabric_/api/v3/entities/{entity_key}",
            status_code=200,
            json={
                "name": "E",
                "displayName": "E",
                "entityType": "E",
                "isRbacEnabled": False,
                "id": f"{entity_key}",
            },
        )

        entity = service.retrieve_v3(entity_key=str(entity_key))

        assert isinstance(entity, Entity)
        assert entity.id == f"{entity_key}"
        sent = httpx_mock.get_request()
        assert sent is not None
        assert "/v3/entities/" in str(sent.url)

    async def test_retrieve_v3_async_hits_v3_surface(
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
            url=f"{base_url}{org}{tenant}/datafabric_/api/v3/entities/{entity_key}",
            status_code=200,
            json={
                "name": "E",
                "displayName": "E",
                "entityType": "E",
                "isRbacEnabled": False,
                "id": f"{entity_key}",
            },
        )

        entity = await service.retrieve_v3_async(entity_key=str(entity_key))

        assert entity.id == f"{entity_key}"

    def test_retrieve_by_name_v3_hits_v3_surface(
        self,
        httpx_mock: HTTPXMock,
        service: EntitiesService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/datafabric_/api/v3/entities/Customers/metadata",
            status_code=200,
            json={
                "name": "Customers",
                "displayName": "Customers",
                "entityType": "Customers",
                "isRbacEnabled": False,
                "id": "cust-1",
            },
        )

        entity = service.retrieve_by_name_v3("Customers")

        assert entity.name == "Customers"
        sent = httpx_mock.get_request()
        assert sent is not None
        assert "/v3/entities/Customers/metadata" in str(sent.url)

    def test_list_entities_v3_hits_v3_surface(
        self,
        httpx_mock: HTTPXMock,
        service: EntitiesService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/datafabric_/api/v3/entities",
            status_code=200,
            json=[
                {
                    "name": "A",
                    "displayName": "A",
                    "entityType": "A",
                    "isRbacEnabled": False,
                    "id": "a-1",
                }
            ],
        )

        entities = service.list_entities_v3()

        assert [e.name for e in entities] == ["A"]

    def test_create_entity_v3_native_hits_v3_surface(
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
            EntityFieldDataType,
        )

        new_id = str(uuid.uuid4())
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/datafabric_/api/v3/entities",
            method="POST",
            status_code=200,
            json=new_id,
        )

        created = service.create_entity_v3(
            name="ProductCatalog",
            fields=[
                EntityCreateFieldOptions(
                    field_name="productName", type=EntityFieldDataType.STRING
                )
            ],
        )

        assert created == new_id
        sent = httpx_mock.get_request()
        assert sent is not None
        assert str(sent.url).endswith("/v3/entities")

    def test_delete_entity_v3_hits_v3_surface(
        self,
        httpx_mock: HTTPXMock,
        service: EntitiesService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        entity_id = "ent-1"
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/datafabric_/api/v3/entities/{entity_id}",
            method="DELETE",
            status_code=200,
        )

        service.delete_entity_v3(entity_id)

        sent = httpx_mock.get_request()
        assert sent is not None
        assert sent.method == "DELETE"

    def test_update_entity_metadata_v3_hits_v3_surface(
        self,
        httpx_mock: HTTPXMock,
        service: EntitiesService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        entity_id = "ent-1"
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/datafabric_/api/v3/entities/{entity_id}/metadata",
            method="PATCH",
            status_code=200,
        )

        service.update_entity_metadata_v3(entity_id, {"display_name": "New"})

        sent = httpx_mock.get_request()
        assert sent is not None
        assert sent.method == "PATCH"
        assert "/v3/entities/ent-1/metadata" in str(sent.url)

    def test_list_records_v3_hits_v3_surface(
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
                rf"{base_url}{org}{tenant}/datafabric_/api/v3/entities/entity/{entity_key}/read.*"
            ),
            status_code=200,
            json={"value": [{"Id": "1"}], "totalRecordCount": 1},
        )

        result = service.list_records_v3(entity_key=str(entity_key), start=0, limit=1)

        assert result.total_count == 1
        sent = httpx_mock.get_request()
        assert sent is not None
        assert "/v3/entities/entity/" in str(sent.url)

    def test_insert_record_v3_hits_v3_surface(
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
                rf"{base_url}{org}{tenant}/datafabric_/api/v3/entities/entity/{entity_key}/insert.*"
            ),
            method="POST",
            status_code=200,
            json={"Id": "1", "name": "a"},
        )

        record = service.insert_record_v3(
            entity_key=str(entity_key), data={"name": "a"}
        )

        assert record.id == "1"

    def test_get_record_v3_hits_v3_surface(
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
            url=f"{base_url}{org}{tenant}/datafabric_/api/v3/entities/entity/{entity_key}/read/7",
            status_code=200,
            json={"Id": "7"},
        )

        record = service.get_record_v3(entity_key=str(entity_key), record_id="7")

        assert record.id == "7"

    def test_update_record_v3_hits_v3_surface(
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
            url=f"{base_url}{org}{tenant}/datafabric_/api/v3/entities/entity/{entity_key}/update/7",
            method="POST",
            status_code=200,
            json={"Id": "7", "name": "u"},
        )

        record = service.update_record_v3(
            entity_key=str(entity_key), record_id="7", data={"name": "u"}
        )

        assert record.id == "7"

    def test_delete_record_v3_hits_v3_surface(
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
            url=f"{base_url}{org}{tenant}/datafabric_/api/v3/entities/entity/{entity_key}/delete/7",
            method="DELETE",
            status_code=200,
        )

        service.delete_record_v3(entity_key=str(entity_key), record_id="7")

        sent = httpx_mock.get_request()
        assert sent is not None
        assert sent.method == "DELETE"

    def test_insert_records_v3_hits_v3_surface(
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
                rf"{base_url}{org}{tenant}/datafabric_/api/v3/entities/entity/{entity_key}/insert-batch.*"
            ),
            method="POST",
            status_code=200,
            json={"successRecords": [{"Id": "1"}], "failureRecords": []},
        )

        result = service.insert_records_v3(
            entity_key=str(entity_key), records=[{"name": "a"}]
        )

        assert len(result.success_records) == 1

    def test_update_records_v3_hits_v3_surface(
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
            url=f"{base_url}{org}{tenant}/datafabric_/api/v3/entities/entity/{entity_key}/update-batch",
            method="POST",
            status_code=200,
            json={"successRecords": [{"Id": "1"}], "failureRecords": []},
        )

        result = service.update_records_v3(
            entity_key=str(entity_key), records=[{"Id": "1", "name": "x"}]
        )

        assert len(result.success_records) == 1

    def test_delete_records_v3_hits_v3_surface(
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
            url=f"{base_url}{org}{tenant}/datafabric_/api/v3/entities/entity/{entity_key}/delete-batch",
            method="POST",
            status_code=200,
            json={"successRecords": [{"Id": "1"}], "failureRecords": []},
        )

        result = service.delete_records_v3(entity_key=str(entity_key), record_ids=["1"])

        assert len(result.success_records) == 1

    def test_v1_methods_emit_deprecation_warning(
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
                "name": "E",
                "displayName": "E",
                "entityType": "E",
                "isRbacEnabled": False,
                "id": f"{entity_key}",
            },
        )

        with pytest.warns(DeprecationWarning):
            service.retrieve(entity_key=str(entity_key))

    async def test_resolve_entity_set_v3_uses_v3_metadata_reads(
        self,
        config: UiPathApiConfig,
        execution_context: UiPathExecutionContext,
    ) -> None:
        folders_service = MagicMock()
        folders_service.retrieve_key_async = AsyncMock(return_value="resolved-folder")
        service = EntitiesService(
            config=config,
            execution_context=execution_context,
            folders_service=folders_service,
        )
        service.retrieve_by_name_v3_async = AsyncMock(  # type: ignore[method-assign]
            return_value=MagicMock(spec=Entity)
        )
        service.retrieve_by_name_async = AsyncMock(  # type: ignore[method-assign]
            return_value=MagicMock(spec=Entity)
        )

        overwrite = EntityResourceOverwrite(
            resource_type="entity",
            name="Customers",
            folder_path="Shared/Finance",
        )
        token = _resource_overwrites.set({"entity.e1": overwrite})
        try:
            resolution = await service.resolve_entity_set_v3_async(
                [DataFabricEntityItem(id="e1", name="Customers", folder_key="fk")]
            )
        finally:
            _resource_overwrites.reset(token)

        assert resolution.entities is not None
        service.retrieve_by_name_v3_async.assert_awaited_once()
        service.retrieve_by_name_async.assert_not_awaited()

    def test_query_v3_by_id_with_filter_and_pagination(
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
                rf"{base_url}{org}{tenant}/datafabric_/api/v3/entities/entity/{entity_key}/query.*"
            ),
            status_code=200,
            json={
                "value": [{"Id": "1", "name": "alice"}, {"Id": "2", "name": "bob"}],
                "totalRecordCount": 5,
            },
        )

        result = service.retrieve_records_v3(
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

    def test_query_binnings_route_to_v3(
        self,
        httpx_mock: HTTPXMock,
        service: EntitiesService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        """Binnings go to the v3 by-id query (which supports them, FF-gated), not v2."""
        from uipath.platform.entities import EntityAggregateFunction, EntityBinning

        entity_key = uuid.uuid4()
        httpx_mock.add_response(
            url=re.compile(
                rf"{base_url}{org}{tenant}/datafabric_/api/v3/entities/entity/{entity_key}/query.*"
            ),
            status_code=200,
            json={"value": [], "totalRecordCount": 0},
        )

        service.retrieve_records_v3(
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
        assert "/v3/entities/entity/" in str(sent.url)
        assert "/v2/" not in str(sent.url)
        body = json.loads(sent.content)
        assert body["binnings"][0]["fieldName"] == "status"

    def test_query_with_joins_routes_to_v1(
        self,
        httpx_mock: HTTPXMock,
        service: EntitiesService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        """Multi-entity joins stay on the v1 by-key endpoint (v3 by-id rejects joins)."""
        from uipath.platform.entities import EntityJoin

        entity_key = uuid.uuid4()
        httpx_mock.add_response(
            url=re.compile(
                rf"{base_url}{org}{tenant}/datafabric_/api/EntityService/entity/{entity_key}/query.*"
            ),
            status_code=200,
            json={"value": [], "totalRecordCount": 0},
        )

        service.retrieve_records_v3(
            entity_key=str(entity_key),
            joins=[
                EntityJoin(
                    entity_name="Order",
                    join_type="LeftJoin",
                    join_field_name="customerId",
                    related_entity_name="Customer",
                    related_field_name="Id",
                )
            ],
        )

        sent = httpx_mock.get_request()
        assert sent is not None
        # v1 by-key path — not the v3 by-id path.
        assert "/api/EntityService/entity/" in str(sent.url)
        assert "/v3/" not in str(sent.url)
        body = json.loads(sent.content)
        assert body["joins"][0]["entityName"] == "Order"

    def test_create_federated_entity_builds_v3_payload(
        self,
        httpx_mock: HTTPXMock,
        service: EntitiesService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        from uipath.platform.entities import (
            EntityClass,
            EntityCreateExternalConnection,
            EntityCreateExternalField,
            EntityCreateExternalFieldMapping,
            EntityCreateExternalObject,
            EntityCreateExternalSource,
            EntityCreateFieldOptions,
            EntityCreateOptions,
            NativeConnectionDetail,
            SourceJoinConditionDetail,
        )

        new_entity_id = str(uuid.uuid4())
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/datafabric_/api/v3/entities",
            method="POST",
            status_code=200,
            json=new_entity_id,
        )

        connector_source = EntityCreateExternalSource(
            external_object_detail=EntityCreateExternalObject(
                external_object_name="sys_user",
                primary_key="sys_id",
                is_primary_source=True,
                method="{}",
            ),
            external_connection_detail=EntityCreateExternalConnection(
                connection_id="conn-1",
                element_instance_id=373410,
                connector_key="uipath-servicenow-servicenow",
                connector_name="ServiceNow",
            ),
            fields=[
                EntityCreateExternalField(
                    field=EntityCreateFieldOptions(field_name="UserName"),
                    external_field_mapping_detail=EntityCreateExternalFieldMapping(
                        external_field_name="user_name"
                    ),
                )
            ],
        )
        native_source = EntityCreateExternalSource(
            external_object_detail=EntityCreateExternalObject(
                external_object_name="UserDept", primary_key="Id"
            ),
            native_connection_detail=NativeConnectionDetail(
                entity_id="dept-entity-id", folder_key="folder-1"
            ),
            fields=[
                EntityCreateExternalField(
                    field=EntityCreateFieldOptions(field_name="Department"),
                    external_field_mapping_detail=EntityCreateExternalFieldMapping(
                        external_field_name="Department"
                    ),
                )
            ],
        )

        created_id = service.create_entity_v3(
            name="UserDirectory",
            fields=[],
            options=EntityCreateOptions(
                entity_class=EntityClass.Federated,
                external_fields=[connector_source, native_source],
                source_join_condition_details=[
                    SourceJoinConditionDetail(
                        source_object_name="sys_user",
                        source_join_field="user_name",
                        source_object_connection_id="conn-1",
                        related_source_object_name="UserDept",
                        related_source_join_field="UserNameDept",
                        related_source_object_connection_id="dept-entity-id",
                    )
                ],
            ),
        )

        assert created_id == new_entity_id
        sent = httpx_mock.get_request()
        assert sent is not None
        definition = json.loads(sent.content)["entityDefinition"]
        # Federated class discriminator (numeric wire id).
        assert definition["entityClassId"] == 10
        # Two sources; the connector source's field wraps in `fieldDefinition`
        # and its mapping uses the numeric directionType.
        sources = definition["externalFields"]
        assert len(sources) == 2
        connector = sources[0]
        assert connector["externalObjectDetail"]["externalObjectName"] == "sys_user"
        assert connector["externalConnectionDetail"]["elementInstanceId"] == 373410
        field = connector["fields"][0]
        assert field["fieldDefinition"]["name"] == "UserName"
        assert field["externalFieldMappingDetail"]["externalFieldName"] == "user_name"
        assert field["externalFieldMappingDetail"]["directionType"] == 0
        # Native source carries its entity reference, not a connector connection.
        assert sources[1]["nativeConnectionDetail"]["entityId"] == "dept-entity-id"
        # Join is passed through in write shape.
        join = definition["sourceJoinConditionDetails"][0]
        assert join["sourceObjectName"] == "sys_user"
        assert join["relatedSourceObjectName"] == "UserDept"
        assert join["joinType"] == "LeftJoin"

    def test_create_federated_entity_requires_sources(
        self, service: EntitiesService
    ) -> None:
        from uipath.platform.entities import EntityClass, EntityCreateOptions

        with pytest.raises(ValueError, match="at least one external source"):
            service.create_entity_v3(
                name="EmptyFederated",
                fields=[],
                options=EntityCreateOptions(entity_class=EntityClass.Federated),
            )

    def test_create_entity_rejects_uncreatable_class(
        self, service: EntitiesService
    ) -> None:
        from uipath.platform.entities import EntityClass, EntityCreateOptions

        with pytest.raises(ValueError, match="is not creatable"):
            service.create_entity_v3(
                name="CaseEntity",
                fields=[],
                options=EntityCreateOptions(entity_class=EntityClass.Case),
            )

    def test_data_direction_type_accepts_legacy_string_names(self) -> None:
        """Legacy string member names normalise to the numeric members (back-compat)."""
        from uipath.platform.entities import (
            DataDirectionType,
            EntityCreateExternalFieldMapping,
        )

        # Legacy string input is intentionally off-type (the field expects the
        # numeric enum); `_missing_` normalises it, so silence the type checker.
        assert DataDirectionType("ReadOnly") is DataDirectionType.ReadOnly  # type: ignore[arg-type]
        assert DataDirectionType("readandwrite") is DataDirectionType.ReadAndWrite  # type: ignore[arg-type]
        assert int(DataDirectionType.ReadOnly) == 0
        # A mapping built from a legacy string serialises to the numeric wire form.
        mapping = EntityCreateExternalFieldMapping(
            external_field_name="user_name",
            direction_type="ReadOnly",  # type: ignore[arg-type]
        )
        dumped = mapping.model_dump(by_alias=True, exclude_none=True, mode="json")
        assert dumped["directionType"] == 0

    async def test_query_async_v3_by_id(
        self, httpx_mock, service, base_url, org, tenant, version
    ) -> None:
        entity_key = uuid.uuid4()
        httpx_mock.add_response(
            url=re.compile(
                rf"{base_url}{org}{tenant}/datafabric_/api/v3/entities/entity/{entity_key}/query"
            ),
            status_code=200,
            json={"value": [{"Id": "1"}], "totalRecordCount": 1},
        )
        result = await service.retrieve_records_v3_async(entity_key=str(entity_key))
        assert result.total_count == 1


def _entity_json(name: str, **extra: object) -> dict[str, object]:
    return {
        "name": name,
        "displayName": name,
        "entityType": "Entity",
        "isRbacEnabled": False,
        "id": f"{name}-id",
        **extra,
    }


class TestEntityOperationsV3:
    def test_v3_metadata_parses_operations(
        self, httpx_mock: HTTPXMock, service: EntitiesService, base_url, org, tenant
    ) -> None:
        operation = {
            "name": "ApproveInvoice",
            "displayName": "Approve invoice",
            "description": "Marks an invoice approved.",
            "kind": "Mutation",
            "implementation": "Code",
            "parameters": [
                {
                    "name": "invoiceId",
                    "sqlType": {"name": "NVARCHAR"},
                    "isRequired": True,
                    "isList": False,
                }
            ],
            "query": None,
        }
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/datafabric_/api/v3/entities/Invoices/metadata",
            json=_entity_json("Invoices", isComposite=False, operations=[operation]),
        )

        entity = service.retrieve_by_name_v3("Invoices")

        assert entity.operations is not None
        [parsed] = entity.operations
        assert (parsed.name, parsed.kind, parsed.implementation) == (
            "ApproveInvoice",
            "Mutation",
            "Code",
        )
        assert parsed.display_name == "Approve invoice"
        [parameter] = parsed.parameters
        assert parameter.name == "invoiceId"
        assert parameter.sql_type == "NVARCHAR"
        assert parameter.is_required is True
        assert parameter.is_list is False
        assert parsed.query is None

    def test_v3_metadata_without_operations(
        self, httpx_mock: HTTPXMock, service: EntitiesService, base_url, org, tenant
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/datafabric_/api/v3/entities/Invoices/metadata",
            json=_entity_json("Invoices"),
        )

        entity = service.retrieve_by_name_v3("Invoices")

        assert entity.operations is None

    async def test_resolve_v3_fetch_by_name_uses_folder_header(
        self, httpx_mock: HTTPXMock, service: EntitiesService, base_url, org, tenant
    ) -> None:
        root = f"{base_url}{org}{tenant}/datafabric_/api/v3/entities"
        httpx_mock.add_response(
            url=f"{root}/Invoices/metadata", json=_entity_json("Invoices")
        )
        httpx_mock.add_response(
            url=f"{root}/Rates/metadata", json=_entity_json("Rates")
        )

        resolution = await service.resolve_entity_set_v3_async(
            [
                DataFabricEntityItem(
                    id="e1", entity_key="k1", name="Invoices", folder_key="fk-1"
                ),
                DataFabricEntityItem(
                    id="e2", entity_key="k2", name="Rates", folder_key=TENANT_FOLDER
                ),
            ],
            fetch_by_name=True,
        )

        assert sorted(e.name for e in resolution.entities) == ["Invoices", "Rates"]
        headers = {
            request.url.path.split("/")[-2]: request.headers
            for request in httpx_mock.get_requests()
        }
        assert headers["Invoices"]["x-uipath-folderkey"] == "fk-1"
        assert "x-uipath-folderkey" not in headers["Rates"]

    def test_resolve_v3_default_fetches_by_key(
        self, httpx_mock: HTTPXMock, service: EntitiesService, base_url, org, tenant
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/datafabric_/api/v3/entities/k1",
            json=_entity_json("Invoices"),
        )

        resolution = service.resolve_entity_set_v3(
            [
                DataFabricEntityItem(
                    id="e1", entity_key="k1", name="Invoices", folder_key="fk-1"
                )
            ]
        )

        assert [e.name for e in resolution.entities] == ["Invoices"]

    def test_invoke_operation_wrote(
        self, httpx_mock: HTTPXMock, service: EntitiesService, base_url, org, tenant
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/datafabric_/api/v3/entities/Invoices/operations/ApproveAll",
            method="POST",
            json={
                "outcome": "Wrote",
                "rowsAffected": 6,
                "edits": [{"kind": "update", "id": "1", "fields": {"Status": "OK"}}],
                "steps": [{"name": "Applying edits", "succeeded": True}],
                "invocationId": 13,
                "prints": ["approved 6"],
                "packageVersion": "1.0.2",
            },
        )

        result = service.invoke_operation(
            "Invoices", "ApproveAll", {"region": "EU"}, folder_key="fk-1"
        )

        assert result.outcome == "Wrote"
        assert result.rows_affected == 6
        assert result.invocation_id == 13
        assert result.prints == ["approved 6"]
        assert result.model_extra == {"packageVersion": "1.0.2"}
        sent = httpx_mock.get_request()
        assert sent is not None
        assert json.loads(sent.content) == {"region": "EU"}
        assert sent.headers["x-uipath-folderkey"] == "fk-1"

    async def test_invoke_operation_refused_is_returned(
        self, httpx_mock: HTTPXMock, service: EntitiesService, base_url, org, tenant
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/datafabric_/api/v3/entities/Invoices/operations/ApproveAll",
            method="POST",
            status_code=400,
            json={
                "outcome": "Refused",
                "rowsAffected": 0,
                "errors": ["invoiceId is required"],
                "steps": [
                    {"name": "Binding parameters", "succeeded": False, "durationMs": 1}
                ],
                "invocationId": 12,
            },
        )

        result = await service.invoke_operation_async("Invoices", "ApproveAll")

        assert result.outcome == "Refused"
        assert result.errors == ["invoiceId is required"]
        assert result.steps[0]["name"] == "Binding parameters"
        sent = httpx_mock.get_request()
        assert sent is not None
        assert json.loads(sent.content) == {}
        assert "x-uipath-folderkey" not in sent.headers

    def test_invoke_operation_not_found_raises(
        self, httpx_mock: HTTPXMock, service: EntitiesService, base_url, org, tenant
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/datafabric_/api/v3/entities/Invoices/operations/Nope",
            method="POST",
            status_code=404,
            json={"error": "Operation not found"},
        )

        with pytest.raises(EnrichedException) as exc_info:
            service.invoke_operation("Invoices", "Nope")

        assert exc_info.value.status_code == 404

    def test_invoke_operation_is_not_retried(
        self, httpx_mock: HTTPXMock, service: EntitiesService, base_url, org, tenant
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/datafabric_/api/v3/entities/Invoices/operations/ApproveAll",
            method="POST",
            status_code=503,
        )

        with pytest.raises(EnrichedException) as exc_info:
            service.invoke_operation("Invoices", "ApproveAll")

        assert exc_info.value.status_code == 503
        assert len(httpx_mock.get_requests()) == 1

    async def test_invoke_operation_async_is_not_retried(
        self, httpx_mock: HTTPXMock, service: EntitiesService, base_url, org, tenant
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/datafabric_/api/v3/entities/Invoices/operations/ApproveAll",
            method="POST",
            status_code=503,
        )

        with pytest.raises(EnrichedException) as exc_info:
            await service.invoke_operation_async("Invoices", "ApproveAll")

        assert exc_info.value.status_code == 503
        assert len(httpx_mock.get_requests()) == 1

    def test_invoke_operation_waits_past_the_invoke_budget(
        self, httpx_mock: HTTPXMock, service: EntitiesService, base_url, org, tenant
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/datafabric_/api/v3/entities/Invoices/operations/ApproveAll",
            method="POST",
            json={"outcome": "Wrote", "rowsAffected": 1},
        )

        service.invoke_operation("Invoices", "ApproveAll")

        sent = httpx_mock.get_request()
        assert sent is not None
        assert sent.extensions["timeout"]["read"] == 150.0

    # The configured name, the overwrite's name as the fetched entity carries it,
    # and a different case all route to the overwrite's folder.
    @pytest.mark.parametrize("invoked_as", ["Invoices", "InvoicesV2", "invoicesv2"])
    def test_invoke_operation_uses_resolved_routing(
        self,
        httpx_mock: HTTPXMock,
        service: EntitiesService,
        base_url,
        org,
        tenant,
        invoked_as: str,
    ) -> None:
        root = f"{base_url}{org}{tenant}/datafabric_/api/v3/entities"
        httpx_mock.add_response(
            url=f"{root}/InvoicesV2/metadata", json=_entity_json("InvoicesV2")
        )
        httpx_mock.add_response(
            url=f"{root}/InvoicesV2/operations/ApproveAll",
            method="POST",
            json={"outcome": "NoChange", "rowsAffected": 0},
        )
        overwrite = EntityResourceOverwrite(
            resource_type="entity", name="InvoicesV2", folder_id="fk-2"
        )
        token = _resource_overwrites.set({"entity.e1": overwrite})
        try:
            resolution = service.resolve_entity_set_v3(
                [DataFabricEntityItem(id="e1", name="Invoices", folder_key="fk-1")]
            )
        finally:
            _resource_overwrites.reset(token)

        result = resolution.entities_service.invoke_operation(invoked_as, "ApproveAll")

        assert result.outcome == "NoChange"
        invoke = httpx_mock.get_requests()[-1]
        assert invoke.url.path.endswith("/v3/entities/InvoicesV2/operations/ApproveAll")
        assert invoke.headers["x-uipath-folderkey"] == "fk-2"
