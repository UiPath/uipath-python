"""Tests for Data Fabric error classification, extraction, and routing."""

import json

import httpx

from uipath.platform.errors import (
    DataFabricError,
    DataFabricErrorCategory,
    EnrichedException,
)
from uipath.platform.errors._datafabric_error import DataFabricSqlValidationError
from uipath.platform.errors._extractors._datafabric import extract_datafabric
from uipath.platform.errors._extractors._router import extract_error_info
from uipath.platform.errors.datafabric_error_codes import classify_error_code

_DATAFABRIC_URL = "https://cloud.uipath.com/org/tenant/datafabric_/api/v1"
_NON_DF_URL = "https://cloud.uipath.com/org/tenant/orchestrator_/api/v1"


def _make_enriched(
    url: str = _DATAFABRIC_URL,
    body: str = "{}",
    status_code: int = 400,
) -> EnrichedException:
    raw = httpx.HTTPStatusError(
        message=f"Server error {status_code}",
        request=httpx.Request("POST", url),
        response=httpx.Response(
            status_code,
            content=body.encode(),
            headers={"content-type": "application/json"},
        ),
    )
    return EnrichedException(raw)


# ---------- classify_error_code ----------


class TestClassifyErrorCode:
    def test_retryable_codes(self) -> None:
        for code in ("EXECUTION_TIMEOUT", "SQLITE_BUSY", "EXECUTION_INTERRUPTED"):
            assert classify_error_code(code) == DataFabricErrorCategory.RETRYABLE

    def test_bad_sql_codes(self) -> None:
        for code in ("SQL_PARSING", "SQL_VALIDATION"):
            assert classify_error_code(code) == DataFabricErrorCategory.BAD_SQL

    def test_client_validation_bad_sql_codes(self) -> None:
        """Pre-flight rejections a rewrite can satisfy classify as bad SQL."""
        for code in (
            "SQL_EMPTY",
            "SQL_MULTIPLE_STATEMENTS",
            "SQL_MISSING_FROM",
            "SQL_LIMIT_REQUIRED",
            "SQL_SELECT_STAR_NOT_ALLOWED",
            "SQL_COUNT_STAR_NOT_SUPPORTED",
            "SQL_TOO_MANY_COLUMNS",
        ):
            assert classify_error_code(code) == DataFabricErrorCategory.BAD_SQL

    def test_unsupported_construct_codes(self) -> None:
        """Rejections of the query shape are distinct from fixable bad SQL."""
        for code in (
            "SQL_STATEMENT_NOT_SELECT",
            "SQL_KEYWORD_NOT_ALLOWED",
            "SQL_CONSTRUCT_NOT_ALLOWED",
            "SQL_SUBQUERY_NOT_ALLOWED",
        ):
            assert (
                classify_error_code(code)
                == DataFabricErrorCategory.UNSUPPORTED_CONSTRUCT
            )

    def test_infrastructure_codes(self) -> None:
        for code in (
            "SQLITE_MEMORY_FULL",
            "EPHEMERAL_STORAGE_ERROR",
            "INTERNAL_ERROR",
            "FQS_ERROR",
        ):
            assert classify_error_code(code) == DataFabricErrorCategory.INFRASTRUCTURE

    def test_data_issue_codes(self) -> None:
        for code in (
            "FRAGMENT_EXECUTION_FAILURE",
            "CONTEXT_CREATION",
            "UNKNOWN_ENTITY",
            "EXECUTION_ERROR",
            "RESULT_TOO_LARGE",
        ):
            assert classify_error_code(code) == DataFabricErrorCategory.DATA_ISSUE

    def test_unknown_code(self) -> None:
        assert classify_error_code("NEVER_HEARD_OF") == DataFabricErrorCategory.UNKNOWN

    def test_none_code(self) -> None:
        assert classify_error_code(None) == DataFabricErrorCategory.UNKNOWN

    def test_empty_string(self) -> None:
        assert classify_error_code("") == DataFabricErrorCategory.UNKNOWN

    def test_case_insensitive(self) -> None:
        assert classify_error_code("sql_parsing") == DataFabricErrorCategory.BAD_SQL
        assert (
            classify_error_code("Execution_Timeout")
            == DataFabricErrorCategory.RETRYABLE
        )


# ---------- DataFabricError ----------


class TestDataFabricError:
    def test_is_retryable(self) -> None:
        err = DataFabricError(
            code="EXECUTION_TIMEOUT",
            message="timed out",
            trace_id="abc",
            category=DataFabricErrorCategory.RETRYABLE,
        )
        assert err.is_retryable is True
        assert err.is_bad_sql is False

    def test_is_bad_sql(self) -> None:
        err = DataFabricError(
            code="SQL_PARSING",
            message="bad sql",
            trace_id="abc",
            category=DataFabricErrorCategory.BAD_SQL,
        )
        assert err.is_bad_sql is True
        assert err.is_retryable is False

    def test_from_response_body(self) -> None:
        body = {
            "error": "something went wrong",
            "code": "INTERNAL_ERROR",
            "traceId": "trace-123",
        }
        err = DataFabricError.from_response_body(body)
        assert err.code == "INTERNAL_ERROR"
        assert err.message == "something went wrong"
        assert err.trace_id == "trace-123"
        assert err.category == DataFabricErrorCategory.INFRASTRUCTURE

    def test_from_response_body_missing_fields(self) -> None:
        err = DataFabricError.from_response_body({})
        assert err.code is None
        assert err.message is None
        assert err.trace_id is None
        assert err.category == DataFabricErrorCategory.UNKNOWN

    def test_from_enriched_exception_datafabric_url(self) -> None:
        body = json.dumps({"error": "bad sql", "code": "SQL_PARSING", "traceId": "t-1"})
        exc = _make_enriched(url=_DATAFABRIC_URL, body=body)
        err = DataFabricError.from_enriched_exception(exc)
        assert err is not None
        assert err.code == "SQL_PARSING"
        assert err.message == "bad sql"
        assert err.trace_id == "t-1"
        assert err.category == DataFabricErrorCategory.BAD_SQL

    def test_from_enriched_exception_non_datafabric_url_returns_none(self) -> None:
        body = json.dumps({"error": "oops", "code": "SQL_PARSING"})
        exc = _make_enriched(url=_NON_DF_URL, body=body)
        assert DataFabricError.from_enriched_exception(exc) is None

    def test_from_enriched_exception_no_error_info(self) -> None:
        exc = _make_enriched(url=_DATAFABRIC_URL, body="not json at all {{{")
        err = DataFabricError.from_enriched_exception(exc)
        assert err is not None
        assert err.code is None
        assert err.message is None
        assert err.category == DataFabricErrorCategory.UNKNOWN


# ---------- extract_datafabric ----------


class TestExtractDatafabric:
    def test_extracts_all_fields(self) -> None:
        body = {"error": "msg", "code": "SQL_PARSING", "traceId": "t-1"}
        info = extract_datafabric(body)
        assert info.message == "msg"
        assert info.error_code == "SQL_PARSING"
        assert info.trace_id == "t-1"

    def test_falls_back_to_message_key(self) -> None:
        body = {"message": "fallback msg", "code": "X"}
        info = extract_datafabric(body)
        assert info.message == "fallback msg"

    def test_missing_fields(self) -> None:
        info = extract_datafabric({})
        assert info.message is None
        assert info.error_code is None
        assert info.trace_id is None


# ---------- Router: datafabric prefix ----------


class TestRouterDatafabric:
    def test_routes_to_datafabric_extractor(self) -> None:
        body = json.dumps(
            {"error": "timeout", "code": "EXECUTION_TIMEOUT", "traceId": "t-2"}
        )
        info = extract_error_info(_DATAFABRIC_URL, body)
        assert info is not None
        assert info.error_code == "EXECUTION_TIMEOUT"
        assert info.trace_id == "t-2"

    def test_non_json_returns_none(self) -> None:
        assert extract_error_info(_DATAFABRIC_URL, "not json") is None


# ---------- Client-side SQL validation ----------


class TestDataFabricSqlValidationError:
    def test_is_a_value_error(self) -> None:
        """Callers catching ValueError keep working."""
        exc = DataFabricSqlValidationError(
            "Subqueries are not allowed.", code="SQL_SUBQUERY_NOT_ALLOWED"
        )
        assert isinstance(exc, ValueError)
        assert str(exc) == "Subqueries are not allowed."

    def test_carries_a_datafabric_error(self) -> None:
        exc = DataFabricSqlValidationError(
            "Subqueries are not allowed.", code="SQL_SUBQUERY_NOT_ALLOWED"
        )
        assert exc.error.code == "SQL_SUBQUERY_NOT_ALLOWED"
        assert exc.error.message == "Subqueries are not allowed."
        assert exc.error.trace_id is None
        assert exc.error.category == DataFabricErrorCategory.UNSUPPORTED_CONSTRUCT
        assert exc.error.is_unsupported_construct is True
        assert exc.error.is_bad_sql is False

    def test_fixable_rejection_is_bad_sql(self) -> None:
        exc = DataFabricSqlValidationError(
            "Queries without WHERE must include a LIMIT clause.",
            code="SQL_LIMIT_REQUIRED",
        )
        assert exc.error.is_bad_sql is True
        assert exc.error.is_unsupported_construct is False


class TestFromException:
    def test_extracts_from_validation_error(self) -> None:
        exc = DataFabricSqlValidationError(
            "SQL construct 'UNION' is not allowed in entity queries.",
            code="SQL_CONSTRUCT_NOT_ALLOWED",
        )
        err = DataFabricError.from_exception(exc)
        assert err is not None
        assert err.category == DataFabricErrorCategory.UNSUPPORTED_CONSTRUCT

    def test_extracts_from_enriched_exception(self) -> None:
        body = json.dumps(
            {"error": "bad sql", "code": "SQL_VALIDATION", "traceId": "t-9"}
        )
        err = DataFabricError.from_exception(_make_enriched(body=body))
        assert err is not None
        assert err.code == "SQL_VALIDATION"
        assert err.category == DataFabricErrorCategory.BAD_SQL

    def test_non_datafabric_enriched_exception_returns_none(self) -> None:
        assert DataFabricError.from_exception(_make_enriched(url=_NON_DF_URL)) is None

    def test_unrelated_exception_returns_none(self) -> None:
        assert DataFabricError.from_exception(RuntimeError("boom")) is None
        assert DataFabricError.from_exception(ValueError("plain")) is None
