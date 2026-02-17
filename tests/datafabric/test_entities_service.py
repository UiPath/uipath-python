import re
from unittest.mock import AsyncMock, MagicMock

import pytest

from uipath.platform import UiPathApiConfig, UiPathExecutionContext
from uipath.platform.entities._entities_service import EntitiesService


@pytest.fixture
def service() -> EntitiesService:
    config = UiPathApiConfig(base_url="https://test.uipath.com/org/tenant", secret="secret")
    execution_context = UiPathExecutionContext()
    return EntitiesService(config=config, execution_context=execution_context)


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
    sql_query: str, error_message: str, service: EntitiesService
) -> None:
    with pytest.raises(ValueError, match=re.escape(error_message)):
        service._validate_sql_query(sql_query)


def test_query_multiple_entities_rejects_invalid_sql_before_network_call(
    service: EntitiesService,
) -> None:
    service.request = MagicMock()  # type: ignore[method-assign]

    with pytest.raises(
        ValueError, match=re.escape("Only SELECT statements are allowed.")
    ):
        service.query_multiple_entities("UPDATE Customers SET name = 'X'")

    service.request.assert_not_called()  # type: ignore[attr-defined]


def test_query_multiple_entities_calls_request_for_valid_sql(
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
