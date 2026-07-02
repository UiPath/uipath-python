"""Data Fabric query engine error classification.

Maps error codes from the DF query engine invoking the "query_execute" endpoint to actionable
categories so that callers (e.g. the agent SQL sub-graph) can decide
whether to retry, ask the LLM to fix the SQL, or surface an infra error.

The server error response JSON has the shape:
    {"error": "<message>", "code": "<ERROR_CODE>", "traceId": "<uuid>"}
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, TypeVar

from ._extractors._helpers import extract_service_prefix
from .datafabric_error_codes import (
    _QUERY_ENTITY_RECORDS_ERROR_CODES,
    DataFabricErrorCategory,
    classify_error_code,
)

if TYPE_CHECKING:
    from ._enriched_exception import EnrichedException


TCallable = TypeVar("TCallable", bound=Callable[..., Any])


def attach_datafabric_error_mapping(
    method_name: str,
) -> Callable[[TCallable], TCallable]:
    """Attach Data Fabric error metadata to a query method."""

    def decorator(func: TCallable) -> TCallable:
        func.__uipath_datafabric_method__ = method_name  # type: ignore[attr-defined]
        func.__uipath_datafabric_error_codes__ = (  # type: ignore[attr-defined]
            _QUERY_ENTITY_RECORDS_ERROR_CODES
        )
        return func

    return decorator


@dataclass(frozen=True)
class DataFabricError:
    """Structured error parsed from a DF query engine response."""

    code: str | None
    message: str | None
    trace_id: str | None
    category: DataFabricErrorCategory

    @property
    def is_retryable(self) -> bool:
        return self.category == DataFabricErrorCategory.RETRYABLE

    @property
    def is_bad_sql(self) -> bool:
        return self.category == DataFabricErrorCategory.BAD_SQL

    @staticmethod
    def from_enriched_exception(exc: EnrichedException) -> DataFabricError | None:
        """Extract a DataFabricError from an EnrichedException, if applicable.

        Returns None if the exception is not from a Data Fabric endpoint.
        """
        if extract_service_prefix(exc.url) != "datafabric_":
            return None

        info = exc.error_info
        code = info.error_code if info else None
        message = info.message if info else None
        trace_id = info.trace_id if info else None

        return DataFabricError(
            code=code,
            message=message,
            trace_id=trace_id,
            category=classify_error_code(code),
        )

    @staticmethod
    def from_response_body(body: dict[str, Any]) -> DataFabricError:
        """Parse a DataFabricError directly from a response body dict."""
        raw_code = body.get("code")
        code = (
            str(raw_code)
            if raw_code is not None and not isinstance(raw_code, (dict, list))
            else None
        )
        message = body.get("error")
        if not isinstance(message, str):
            message = (
                body.get("message") if isinstance(body.get("message"), str) else None
            )
        trace_id = body.get("traceId")
        if not isinstance(trace_id, str):
            trace_id = (
                body.get("requestId")
                if isinstance(body.get("requestId"), str)
                else None
            )
        return DataFabricError(
            code=code,
            message=message,
            trace_id=trace_id,
            category=classify_error_code(code),
        )
