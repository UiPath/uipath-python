"""Helpers for serializing and deserializing OpenTelemetry spans for storage."""

from typing import Any

from opentelemetry.sdk.trace import Event, ReadableSpan
from opentelemetry.trace import SpanContext, SpanKind, Status, StatusCode, TraceFlags


def serialize_span(span: ReadableSpan) -> dict[str, Any]:
    """Serialize a ReadableSpan to a JSON-compatible dict for storage."""
    ctx = span.context
    context_data = None
    if ctx:
        context_data = {
            "trace_id": ctx.trace_id,
            "span_id": ctx.span_id,
            "trace_flags": int(ctx.trace_flags),
        }

    parent_data = None
    if span.parent:
        parent_data = {
            "trace_id": span.parent.trace_id,
            "span_id": span.parent.span_id,
            "trace_flags": int(span.parent.trace_flags),
        }

    attrs: dict[str, Any] = {}
    if span.attributes:
        for k, v in span.attributes.items():
            attrs[k] = list(v) if isinstance(v, tuple) else v

    events_data = []
    if span.events:
        for e in span.events:
            event_attrs: dict[str, Any] = {}
            if e.attributes:
                for k, v in e.attributes.items():
                    event_attrs[k] = list(v) if isinstance(v, tuple) else v
            events_data.append(
                {
                    "name": e.name,
                    "attributes": event_attrs,
                    "timestamp": e.timestamp,
                }
            )

    return {
        "name": span.name,
        "context": context_data,
        "parent": parent_data,
        "attributes": attrs,
        "events": events_data,
        "status_code": span.status.status_code.value if span.status else 0,
        "status_description": span.status.description if span.status else None,
        "start_time": span.start_time,
        "end_time": span.end_time,
        "kind": span.kind.value if span.kind else 0,
    }


def deserialize_span(data: dict[str, Any]) -> ReadableSpan:
    """Deserialize a dict back to a ReadableSpan."""
    context = None
    if data.get("context"):
        context = SpanContext(
            trace_id=data["context"]["trace_id"],
            span_id=data["context"]["span_id"],
            is_remote=False,
            trace_flags=TraceFlags(data["context"].get("trace_flags", 0)),
        )

    parent = None
    if data.get("parent"):
        parent = SpanContext(
            trace_id=data["parent"]["trace_id"],
            span_id=data["parent"]["span_id"],
            is_remote=False,
            trace_flags=TraceFlags(data["parent"].get("trace_flags", 0)),
        )

    status = Status(
        status_code=StatusCode(data.get("status_code", 0)),
        description=data.get("status_description"),
    )

    events = []
    for e in data.get("events", []):
        events.append(
            Event(
                name=e["name"],
                attributes=e.get("attributes"),
                timestamp=e.get("timestamp"),
            )
        )

    return ReadableSpan(
        name=data["name"],
        context=context,
        parent=parent,
        attributes=data.get("attributes"),
        events=events,
        status=status,
        start_time=data.get("start_time"),
        end_time=data.get("end_time"),
        kind=SpanKind(data.get("kind", 0)),
    )
