"""Data Fabric query-engine error code constants."""

from __future__ import annotations

from enum import Enum

_RETRYABLE_CODES: frozenset[str] = frozenset(
    {
        "EXECUTION_TIMEOUT",
        "SQLITE_BUSY",
        "EXECUTION_INTERRUPTED",
    }
)

_BAD_SQL_CODES: frozenset[str] = frozenset(
    {
        "SQL_PARSING",
        "SQL_VALIDATION",
    }
)

_INFRASTRUCTURE_CODES: frozenset[str] = frozenset(
    {
        "SQLITE_MEMORY_FULL",
        "EPHEMERAL_STORAGE_ERROR",
        "INTERNAL_ERROR",
        "FQS_ERROR",
    }
)

_DATA_ISSUE_CODES: frozenset[str] = frozenset(
    {
        "FRAGMENT_EXECUTION_FAILURE",
        "CONTEXT_CREATION",
        "UNKNOWN_ENTITY",
        "EXECUTION_ERROR",
        "RESULT_TOO_LARGE",
    }
)

_QUERY_ENTITY_RECORDS_ERROR_CODES: frozenset[str] = frozenset(
    {*_RETRYABLE_CODES, *_BAD_SQL_CODES, *_INFRASTRUCTURE_CODES, *_DATA_ISSUE_CODES}
)


class DataFabricErrorCategory(str, Enum):
    """Actionable error category for Data Fabric query failures."""

    RETRYABLE = "retryable"
    BAD_SQL = "bad_sql"
    INFRASTRUCTURE = "infrastructure"
    DATA_ISSUE = "data_issue"
    UNKNOWN = "unknown"


def classify_error_code(code: str | None) -> DataFabricErrorCategory:
    """Classify a DF error code string into an actionable category."""
    if not code:
        return DataFabricErrorCategory.UNKNOWN
    upper = code.upper()
    if upper in _RETRYABLE_CODES:
        return DataFabricErrorCategory.RETRYABLE
    if upper in _BAD_SQL_CODES:
        return DataFabricErrorCategory.BAD_SQL
    if upper in _INFRASTRUCTURE_CODES:
        return DataFabricErrorCategory.INFRASTRUCTURE
    if upper in _DATA_ISSUE_CODES:
        return DataFabricErrorCategory.DATA_ISSUE
    return DataFabricErrorCategory.UNKNOWN
