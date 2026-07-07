"""Tests for the v2 entities facade (``sdk.entities_v2``)."""

import pytest
from pytest_httpx import HTTPXMock

from uipath.platform import UiPathApiConfig, UiPathExecutionContext
from uipath.platform.entities import (
    EntitiesServiceV2,
    EntityQueryFilter,
    EntityQueryFilterGroup,
    QueryFilterOperator,
    RetrieveEntityRecordsResponse,
)


@pytest.fixture
def service_v2(
    config: UiPathApiConfig, execution_context: UiPathExecutionContext
) -> EntitiesServiceV2:
    return EntitiesServiceV2(config=config, execution_context=execution_context)


def test_retrieve_records_hits_v2_endpoint(
    service_v2: EntitiesServiceV2,
    httpx_mock: HTTPXMock,
    base_url: str,
    org: str,
    tenant: str,
) -> None:
    entity_key = "Customers"
    httpx_mock.add_response(
        url=f"{base_url}{org}{tenant}/datafabric_/api/v2/EntityService/entity/{entity_key}/query",
        method="POST",
        json={"value": [{"Id": "r1", "name": "Alice"}], "totalRecordCount": 1},
    )

    result = service_v2.retrieve_records(
        entity_key,
        filter_group=EntityQueryFilterGroup(
            query_filters=[
                EntityQueryFilter(
                    field_name="status",
                    operator=QueryFilterOperator.Equals,
                    value="active",
                )
            ]
        ),
    )

    assert isinstance(result, RetrieveEntityRecordsResponse)
    assert result.total_count == 1
    assert result.items[0].id == "r1"
    sent = httpx_mock.get_request()
    assert sent is not None
    assert "/datafabric_/api/v2/EntityService/entity/Customers/query" in str(sent.url)


def test_get_record_hits_v2_endpoint(
    service_v2: EntitiesServiceV2,
    httpx_mock: HTTPXMock,
    base_url: str,
    org: str,
    tenant: str,
) -> None:
    httpx_mock.add_response(
        url=f"{base_url}{org}{tenant}/datafabric_/api/v2/EntityService/entity/Customers/read/rec-1",
        method="GET",
        json={"Id": "rec-1", "name": "Alice"},
    )

    record = service_v2.get_record("Customers", "rec-1")

    assert record.id == "rec-1"
    sent = httpx_mock.get_request()
    assert "/datafabric_/api/v2/EntityService/entity/Customers/read/rec-1" in str(
        sent.url
    )


def test_list_entities_hits_v2_endpoint(
    service_v2: EntitiesServiceV2,
    httpx_mock: HTTPXMock,
    base_url: str,
    org: str,
    tenant: str,
) -> None:
    httpx_mock.add_response(
        url=f"{base_url}{org}{tenant}/datafabric_/api/v2/Entity",
        method="GET",
        json=[
            {
                "name": "Customers",
                "displayName": "Customers",
                "entityType": "Entity",
                "isRbacEnabled": False,
                "id": "e1",
            }
        ],
    )

    entities = service_v2.list_entities()

    assert len(entities) == 1
    assert entities[0].name == "Customers"
    assert "/datafabric_/api/v2/Entity" in str(httpx_mock.get_request().url)


def test_v2_omits_unsupported_operations(service_v2: EntitiesServiceV2) -> None:
    # v2 is a limited surface: write/batch/attachment/schema-write ops are not
    # exposed because the backend does not implement them.
    for name in (
        "insert_record",
        "update_record",
        "delete_record",
        "insert_records",
        "delete_records",
        "create_entity",
        "upload_attachment",
        "get_choiceset_values",
    ):
        assert not hasattr(service_v2, name), f"v2 should not expose {name}"


async def test_retrieve_records_async_hits_v2_endpoint(
    service_v2: EntitiesServiceV2,
    httpx_mock: HTTPXMock,
    base_url: str,
    org: str,
    tenant: str,
) -> None:
    httpx_mock.add_response(
        url=f"{base_url}{org}{tenant}/datafabric_/api/v2/EntityService/entity/Customers/query",
        method="POST",
        json={"value": [], "totalRecordCount": 0},
    )

    result = await service_v2.retrieve_records_async("Customers")

    assert isinstance(result, RetrieveEntityRecordsResponse)
    assert result.total_count == 0
