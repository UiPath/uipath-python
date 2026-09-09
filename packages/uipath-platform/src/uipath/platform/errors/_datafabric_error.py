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

    @property
    def is_unsupported_construct(self) -> bool:
        """True when the entity-query subset cannot express this query shape.

        Distinct from :attr:`is_bad_sql`: a bad statement can be fixed by
        rewriting the SQL, whereas an unsupported construct means retrying a
        variant of the same approach will fail again.
        """
        return self.category == DataFabricErrorCategory.UNSUPPORTED_CONSTRUCT

    @staticmethod
    def from_exception(exc: BaseException) -> DataFabricError | None:
        """Extract a DataFabricError from any Data Fabric query failure.

        Covers both origins of a failed query so callers need one branch:
        client-side validation rejections raised before the request, and
        server-side errors returned by the query engine.

        Returns None if the exception is not a Data Fabric query failure.
        """
        if isinstance(exc, DataFabricSqlValidationError):
            return exc.error
        from ._enriched_exception import EnrichedException as _EnrichedException

        if isinstance(exc, _EnrichedException):
            return DataFabricError.from_enriched_exception(exc)
        return None

    @staticmethod
    def from_validation(code: str, message: str) -> DataFabricError:
        """Build a DataFabricError for a client-side validation rejection.

        These never reach the query engine, so there is no trace id; the code
        is classified through the same table as server-returned codes.
        """
        return DataFabricError(
            code=code,
            message=message,
            trace_id=None,
            category=classify_error_code(code),
        )

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


class DataFabricSqlValidationError(ValueError):
    """A SQL statement rejected by client-side entity-query validation.

    A thin carrier: the classification callers act on is the
    :class:`DataFabricError` on :attr:`error`, the same type server-side
    failures produce. Remains a :class:`ValueError` subclass so existing
    callers catching ``ValueError`` are unaffected; reach the structured form
    with :meth:`DataFabricError.from_exception`.
    """

    def __init__(self, message: str, *, code: str) -> None:
        """Initialise the error.

        Args:
            message: Human-readable rejection reason.
            code: Stable code for this rejection, classified into a
                :class:`DataFabricErrorCategory` by the shared code table.
        """
        super().__init__(message)
        self.error = DataFabricError.from_validation(code=code, message=message)
