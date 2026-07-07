"""Tests for the v3 entities facade (``sdk.entities_v3``) and v3 models."""

import pytest
from pytest_httpx import HTTPXMock

from uipath.platform import UiPathApiConfig, UiPathExecutionContext
from uipath.platform.entities import (
    BatchOperationResponse,
    CompositeEntityMetadataResponse,
    EntitiesServiceV3,
    EntityRecordV3,
    EntityWriteResponseV3,
    GetAllResponseV3,
    QueryResponseV3,
)

_V3 = "datafabric_/api/v3/entities"


@pytest.fixture
def service_v3(
    config: UiPathApiConfig, execution_context: UiPathExecutionContext
) -> EntitiesServiceV3:
    return EntitiesServiceV3(config=config, execution_context=execution_context)


# ---------------------------------------------------------------------------
# Models (unit) — the EntityWriteResponseV3 flattening contract
# ---------------------------------------------------------------------------


def test_write_response_folds_and_reflattens() -> None:
    payload = {
        "Id": "r1",
        "CaseId": "CASE-001",
        "CaseStatus": "Open",
        "children": {},
        "cascadeDeletedChildren": {},
        "deletedCount": 0,
    }
    w = EntityWriteResponseV3.model_validate(payload)
    assert w.id == "r1"
    assert w.root_fields == {"CaseId": "CASE-001", "CaseStatus": "Open"}
    assert w.get("CaseId") == "CASE-001"
    # updatedCount omitted when zero; root fields flattened back to top level
    dumped = w.model_dump()
    assert dumped["Id"] == "r1"
    assert dumped["CaseId"] == "CASE-001"
    assert "updatedCount" not in dumped
    assert dumped["deletedCount"] == 0


def test_write_response_keeps_children_and_updated_count() -> None:
    w = EntityWriteResponseV3.model_validate(
        {
            "Id": "r1",
            "Name": "x",
            "children": {
                "Lines": {"records": [{"Id": "c1"}], "hasMore": True, "ref": None}
            },
            "cascadeDeletedChildren": {"Lines": 2},
            "deletedCount": 0,
            "updatedCount": 3,
        }
    )
    assert w.children["Lines"].has_more is True
    assert w.children["Lines"].records == [{"Id": "c1"}]
    assert w.cascade_deleted_children == {"Lines": 2}
    assert w.updated_count == 3
    assert w.model_dump()["updatedCount"] == 3


# ---------------------------------------------------------------------------
# Data operations
# ---------------------------------------------------------------------------


def test_retrieve_records_v3(
    service_v3: EntitiesServiceV3,
    httpx_mock: HTTPXMock,
    base_url: str,
    org: str,
    tenant: str,
) -> None:
    httpx_mock.add_response(
        url=f"{base_url}{org}{tenant}/{_V3}/Customers/query",
        method="POST",
        json={
            "value": [
                {"Id": "r1", "name": "Alice", "children": {}},
                {"Id": "r2", "name": "Bob", "children": {}},
            ],
            "totalRecordCount": 2,
            "totalRecordCountIsEstimate": False,
        },
    )

    result = service_v3.retrieve_records("Customers", selected_fields=["name"])

    assert isinstance(result, QueryResponseV3)
    assert result.total_record_count == 2
    assert len(result) == 2
    assert result[0].id == "r1"
    assert result[0].get("name") == "Alice"
    assert f"/{_V3}/Customers/query" in str(httpx_mock.get_request().url)


def test_insert_record_v3(
    service_v3: EntitiesServiceV3,
    httpx_mock: HTTPXMock,
    base_url: str,
    org: str,
    tenant: str,
) -> None:
    httpx_mock.add_response(
        url=f"{base_url}{org}{tenant}/{_V3}/Customers/insert",
        method="POST",
        json={"Id": "r1", "name": "Alice", "children": {}, "deletedCount": 0},
    )

    record = service_v3.insert_record("Customers", {"name": "Alice"})

    assert isinstance(record, EntityWriteResponseV3)
    assert record.id == "r1"
    assert record.get("name") == "Alice"
    sent = httpx_mock.get_request()
    assert f"/{_V3}/Customers/insert" in str(sent.url)


def test_get_record_v3_folds_flat_dict(
    service_v3: EntitiesServiceV3,
    httpx_mock: HTTPXMock,
    base_url: str,
    org: str,
    tenant: str,
) -> None:
    httpx_mock.add_response(
        url=f"{base_url}{org}{tenant}/{_V3}/Customers/read/rec-1",
        method="GET",
        json={"Id": "rec-1", "name": "Alice", "age": 30},
    )

    record = service_v3.get_record("Customers", "rec-1")

    assert record.id == "rec-1"
    assert record.root_fields == {"name": "Alice", "age": 30}


def test_update_record_v3(
    service_v3: EntitiesServiceV3,
    httpx_mock: HTTPXMock,
    base_url: str,
    org: str,
    tenant: str,
) -> None:
    httpx_mock.add_response(
        url=f"{base_url}{org}{tenant}/{_V3}/Customers/update/rec-1",
        method="POST",
        json={"Id": "rec-1", "name": "Alice2"},
    )

    record = service_v3.update_record("Customers", "rec-1", {"name": "Alice2"})

    assert record.get("name") == "Alice2"
    assert f"/{_V3}/Customers/update/rec-1" in str(httpx_mock.get_request().url)


def test_delete_record_v3(
    service_v3: EntitiesServiceV3,
    httpx_mock: HTTPXMock,
    base_url: str,
    org: str,
    tenant: str,
) -> None:
    httpx_mock.add_response(
        url=f"{base_url}{org}{tenant}/{_V3}/Customers/delete/rec-1",
        method="DELETE",
        json={"Id": "rec-1", "deletedCount": 1},
    )

    record = service_v3.delete_record("Customers", "rec-1")

    assert record.deleted_count == 1
    sent = httpx_mock.get_request()
    assert sent.method == "DELETE"
    assert f"/{_V3}/Customers/delete/rec-1" in str(sent.url)


def test_insert_records_batch_v3(
    service_v3: EntitiesServiceV3,
    httpx_mock: HTTPXMock,
    base_url: str,
    org: str,
    tenant: str,
) -> None:
    httpx_mock.add_response(
        url=f"{base_url}{org}{tenant}/{_V3}/Customers/insert-batch",
        method="POST",
        json={
            "successRecords": [{"Id": "r1", "name": "Alice"}],
            "failureRecords": [{"error": "dup", "record": {"name": "Bob"}}],
        },
    )

    result = service_v3.insert_records(
        "Customers", [{"name": "Alice"}, {"name": "Bob"}]
    )

    assert isinstance(result, BatchOperationResponse)
    assert result.success_records[0]["Id"] == "r1"
    assert result.failure_records[0].error == "dup"


def test_delete_records_batch_v3_sends_id_list(
    service_v3: EntitiesServiceV3,
    httpx_mock: HTTPXMock,
    base_url: str,
    org: str,
    tenant: str,
) -> None:
    import json

    httpx_mock.add_response(
        url=f"{base_url}{org}{tenant}/{_V3}/Customers/delete-batch",
        method="POST",
        json={"successRecords": [], "failureRecords": []},
    )

    service_v3.delete_records("Customers", ["id-1", "id-2"])

    sent = httpx_mock.get_request()
    assert json.loads(sent.content) == ["id-1", "id-2"]
    assert f"/{_V3}/Customers/delete-batch" in str(sent.url)


def test_list_records_v3_sends_paging(
    service_v3: EntitiesServiceV3,
    httpx_mock: HTTPXMock,
    base_url: str,
    org: str,
    tenant: str,
) -> None:
    httpx_mock.add_response(
        url=f"{base_url}{org}{tenant}/{_V3}/Customers/read?start=0&limit=100",
        method="GET",
        json={"value": [{"Id": "r1"}], "totalRecordCount": 1},
    )

    result = service_v3.list_records("Customers")

    assert isinstance(result, QueryResponseV3)
    assert result[0].id == "r1"


def test_upload_attachment_v3_endpoint(
    service_v3: EntitiesServiceV3,
    httpx_mock: HTTPXMock,
    base_url: str,
    org: str,
    tenant: str,
) -> None:
    httpx_mock.add_response(
        url=f"{base_url}{org}{tenant}/{_V3}/Customers/records/rec-1/attachments/Contract",
        method="POST",
        json={"Id": "rec-1"},
    )

    service_v3.upload_attachment("Customers", "rec-1", "Contract", file=b"data")

    sent = httpx_mock.get_request()
    assert "/records/rec-1/attachments/Contract" in str(sent.url)


def test_import_records_not_supported_in_v3(service_v3: EntitiesServiceV3) -> None:
    with pytest.raises(NotImplementedError):
        service_v3.import_records("Customers", file=b"csv")


# ---------------------------------------------------------------------------
# Schema operations
# ---------------------------------------------------------------------------


def test_list_entities_v3(
    service_v3: EntitiesServiceV3,
    httpx_mock: HTTPXMock,
    base_url: str,
    org: str,
    tenant: str,
) -> None:
    httpx_mock.add_response(
        url=f"{base_url}{org}{tenant}/{_V3}",
        method="GET",
        json=[
            {
                "name": "Customers",
                "displayName": "Customers",
                "entityType": "Entity",
                "isRbacEnabled": False,
                "id": "e1",
                "entityClass": "Native",
            }
        ],
    )

    entities = service_v3.list_entities()

    assert isinstance(entities[0], EntityRecordV3)
    assert entities[0].entity_class == "Native"


def test_retrieve_by_name_v3_metadata(
    service_v3: EntitiesServiceV3,
    httpx_mock: HTTPXMock,
    base_url: str,
    org: str,
    tenant: str,
) -> None:
    httpx_mock.add_response(
        url=f"{base_url}{org}{tenant}/{_V3}/Orders/metadata",
        method="GET",
        json={
            "name": "Orders",
            "displayName": "Orders",
            "entityType": "Entity",
            "isRbacEnabled": False,
            "id": "e2",
            "isComposite": True,
            "compositeInfo": {
                "entityId": "e2",
                "rootEntityName": "Orders",
                "members": [
                    {"entityId": "e2", "entityName": "Orders", "isRoot": True},
                    {
                        "entityId": "e3",
                        "entityName": "OrderLines",
                        "isRoot": False,
                        "parentEntityName": "Orders",
                    },
                ],
            },
        },
    )

    meta = service_v3.retrieve_by_name("Orders")

    assert isinstance(meta, CompositeEntityMetadataResponse)
    assert meta.is_composite is True
    assert meta.composite_info is not None
    assert len(meta.composite_info.members) == 2
    assert meta.composite_info.members[1].entity_name == "OrderLines"


def test_get_all_v3(
    service_v3: EntitiesServiceV3,
    httpx_mock: HTTPXMock,
    base_url: str,
    org: str,
    tenant: str,
) -> None:
    httpx_mock.add_response(
        url=f"{base_url}{org}{tenant}/{_V3}/all?start=0&limit=1000",
        method="GET",
        json={
            "entities": [
                {
                    "name": "Customers",
                    "displayName": "Customers",
                    "entityType": "Entity",
                    "isRbacEnabled": False,
                    "id": "e1",
                }
            ],
            "choicesets": [{"id": "cs1", "name": "Colors"}],
        },
    )

    catalog = service_v3.get_all()

    assert isinstance(catalog, GetAllResponseV3)
    assert catalog.entities[0].name == "Customers"
    assert catalog.choicesets[0]["name"] == "Colors"


def test_create_entity_v3_posts_to_v3(
    service_v3: EntitiesServiceV3,
    httpx_mock: HTTPXMock,
    base_url: str,
    org: str,
    tenant: str,
) -> None:
    from uipath.platform.entities import EntityCreateFieldOptions, EntityFieldDataType

    httpx_mock.add_response(
        url=f"{base_url}{org}{tenant}/{_V3}",
        method="POST",
        json="new-entity-id",
    )

    entity_id = service_v3.create_entity(
        "Products",
        [EntityCreateFieldOptions(field_name="title", type=EntityFieldDataType.STRING)],
    )

    assert entity_id == "new-entity-id"
    assert str(httpx_mock.get_request().url).endswith(f"/{_V3}")


async def test_insert_record_async_v3(
    service_v3: EntitiesServiceV3,
    httpx_mock: HTTPXMock,
    base_url: str,
    org: str,
    tenant: str,
) -> None:
    httpx_mock.add_response(
        url=f"{base_url}{org}{tenant}/{_V3}/Customers/insert",
        method="POST",
        json={"Id": "r1", "name": "Async"},
    )

    record = await service_v3.insert_record_async("Customers", {"name": "Async"})

    assert record.get("name") == "Async"
