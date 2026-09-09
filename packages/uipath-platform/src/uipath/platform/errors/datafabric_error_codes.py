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
        # Client-side pre-flight rejections that a rewrite can satisfy.
        "SQL_EMPTY",
        "SQL_MULTIPLE_STATEMENTS",
        "SQL_MISSING_FROM",
        "SQL_LIMIT_REQUIRED",
        "SQL_SELECT_STAR_NOT_ALLOWED",
        "SQL_COUNT_STAR_NOT_SUPPORTED",
        "SQL_TOO_MANY_COLUMNS",
    }
)

_UNSUPPORTED_CONSTRUCT_CODES: frozenset[str] = frozenset(
    {
        # Client-side pre-flight rejections of the query *shape*. The entity
        # query subset cannot express these at all, so retrying a variant of
        # the same approach fails again — the caller must change strategy or
        # tell the user the question is not answerable here.
        "SQL_STATEMENT_NOT_SELECT",
        "SQL_KEYWORD_NOT_ALLOWED",
        "SQL_CONSTRUCT_NOT_ALLOWED",
        "SQL_SUBQUERY_NOT_ALLOWED",
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
    {
        *_RETRYABLE_CODES,
        *_BAD_SQL_CODES,
        *_UNSUPPORTED_CONSTRUCT_CODES,
        *_INFRASTRUCTURE_CODES,
        *_DATA_ISSUE_CODES,
    }
)


class DataFabricErrorCategory(str, Enum):
    """Actionable error category for Data Fabric query failures."""

    RETRYABLE = "retryable"
    BAD_SQL = "bad_sql"
    UNSUPPORTED_CONSTRUCT = "unsupported_construct"
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
    if upper in _UNSUPPORTED_CONSTRUCT_CODES:
        return DataFabricErrorCategory.UNSUPPORTED_CONSTRUCT
    if upper in _INFRASTRUCTURE_CODES:
        return DataFabricErrorCategory.INFRASTRUCTURE
    if upper in _DATA_ISSUE_CODES:
        return DataFabricErrorCategory.DATA_ISSUE
    return DataFabricErrorCategory.UNKNOWN
