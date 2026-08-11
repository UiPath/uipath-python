"""Tests for Data Fabric error classification, extraction, and routing."""

import json

import httpx

from uipath.platform.errors import (
    DataFabricError,
    DataFabricErrorCategory,
    EnrichedException,
)
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
