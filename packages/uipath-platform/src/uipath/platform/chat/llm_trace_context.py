"""W3C-style trace context headers for LLM Gateway requests."""

from opentelemetry import trace
from uipath.core.feature_flags import FeatureFlags

from ..common._config import UiPathConfig


def build_trace_context_headers(
    extra_baggage: list[str] | None = None,
) -> dict[str, str]:
    """Build W3C-style trace context headers from the current OpenTelemetry span.

    Args:
        extra_baggage: Additional baggage entries (e.g. ``["source=agents"]``)
            that callers can inject alongside the platform-level entries.

    Returns an empty dict when the ``EnableTraceContextHeaders`` feature flag
    is not enabled, or when no active span is present.
    """
    if not FeatureFlags.is_flag_enabled("EnableTraceContextHeaders"):
        return {}

    headers: dict[str, str] = {}
    span = trace.get_current_span()
    ctx = span.get_span_context()
    if ctx and ctx.trace_id and ctx.span_id:
        trace_id = format(ctx.trace_id, "032x")
        span_id = format(ctx.span_id, "016x")
        headers["x-uipath-traceparent-id"] = f"00-{trace_id}-{span_id}"

    baggage_parts: list[str] = list(extra_baggage) if extra_baggage else []
    if folder_key := UiPathConfig.folder_key:
        baggage_parts.append(f"folderKey={folder_key}")
    if agent_id := UiPathConfig.process_uuid:
        baggage_parts.append(f"agentId={agent_id}")
    if process_key := UiPathConfig.process_key:
        baggage_parts.append(f"processKey={process_key}")
    if baggage_parts:
        headers["x-uipath-tracebaggage"] = ",".join(baggage_parts)

    return headers
