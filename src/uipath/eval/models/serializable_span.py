"""JSON-serializable span model for trace data transport across process boundaries."""

import logging
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SerializableSpanEvent(BaseModel):
    """JSON-serializable representation of a span event."""

    name: str
    timestamp: int | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class SerializableSpan(BaseModel):
    """JSON-serializable representation of an OpenTelemetry ReadableSpan.

    Used to transport span data across process boundaries (e.g., from CLI to
    a remote evaluation backend). Preserves full span data including IDs and
    timestamps so that spans can be reconstructed on the receiving end.
    """

    name: str
    span_id: str = Field(description="16-char hex OTEL span ID")
    trace_id: str = Field(description="32-char hex OTEL trace ID")
    parent_span_id: str | None = Field(
        default=None, description="16-char hex parent span ID"
    )
    status: str = Field(
        default="unset", description="Span status: 'unset', 'ok', or 'error'"
    )
    status_description: str | None = Field(
        default=None, description="Status description (typically set for errors)"
    )
    start_time_unix_nano: int = Field(
        default=0, description="Start time in nanoseconds since epoch"
    )
    end_time_unix_nano: int = Field(
        default=0, description="End time in nanoseconds since epoch"
    )
    attributes: dict[str, Any] = Field(default_factory=dict)
    events: list[SerializableSpanEvent] = Field(default_factory=list)

    @classmethod
    def from_readable_span(cls, span: Any) -> "SerializableSpan":
        """Convert an OpenTelemetry ReadableSpan to a SerializableSpan.

        Args:
            span: An OpenTelemetry ReadableSpan instance.

        Returns:
            SerializableSpan with all relevant data extracted.
        """
        try:
            span_context = span.get_span_context()
            span_id = format(span_context.span_id, "016x")
            trace_id = format(span_context.trace_id, "032x")
        except Exception:
            logger.warning(
                f"Failed to extract span context from span '{getattr(span, 'name', '?')}', "
                "using zero IDs"
            )
            span_id = "0" * 16
            trace_id = "0" * 32

        # Extract parent span ID
        parent_span_id = None
        if span.parent is not None:
            try:
                parent_span_id = format(span.parent.span_id, "016x")
            except Exception:
                pass

        # Extract status
        status_map = {0: "unset", 1: "ok", 2: "error"}
        try:
            status = status_map.get(span.status.status_code.value, "unknown")
            status_description = span.status.description
        except Exception:
            status = "unset"
            status_description = None

        # Extract timestamps
        start_time_unix_nano = span.start_time or 0
        end_time_unix_nano = span.end_time or 0

        # Extract attributes
        attributes: dict[str, Any] = {}
        if span.attributes:
            for key, value in span.attributes.items():
                try:
                    attributes[key] = _make_json_safe(value)
                except Exception:
                    logger.debug(f"Skipping non-serializable attribute '{key}'")

        # Extract events
        events: list[SerializableSpanEvent] = []
        if hasattr(span, "events") and span.events:
            for event in span.events:
                try:
                    event_attrs = {}
                    if event.attributes:
                        for k, v in event.attributes.items():
                            try:
                                event_attrs[k] = _make_json_safe(v)
                            except Exception:
                                pass
                    events.append(
                        SerializableSpanEvent(
                            name=event.name,
                            timestamp=event.timestamp,
                            attributes=event_attrs,
                        )
                    )
                except Exception:
                    logger.debug(f"Skipping non-serializable event")

        return cls(
            name=span.name,
            span_id=span_id,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            status=status,
            status_description=status_description,
            start_time_unix_nano=start_time_unix_nano,
            end_time_unix_nano=end_time_unix_nano,
            attributes=attributes,
            events=events,
        )


def _make_json_safe(value: Any) -> Any:
    """Convert a value to a JSON-safe representation.

    OpenTelemetry attribute values are constrained to primitives and
    sequences of primitives, so this is straightforward.
    """
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [_make_json_safe(v) for v in value]
    # Fall back to string representation for unknown types
    return str(value)
