"""W3C-style trace context headers for LLM Gateway requests."""

import os

from opentelemetry import trace
from uipath.core.feature_flags import FeatureFlags

from ..common.constants import (
    ENV_FOLDER_KEY,
    ENV_PROCESS_KEY,
    ENV_UIPATH_PROCESS_UUID,
)


def build_trace_context_headers() -> dict[str, str]:
    """Build W3C-style trace context headers from the current OpenTelemetry span.

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

    baggage_parts: list[str] = ["source=agents"]
    if folder_key := os.getenv(ENV_FOLDER_KEY):
        baggage_parts.append(f"folderKey={folder_key}")
    if agent_id := os.getenv(ENV_UIPATH_PROCESS_UUID):
        baggage_parts.append(f"agentId={agent_id}")
    if process_key := os.getenv(ENV_PROCESS_KEY):
        baggage_parts.append(f"processKey={process_key}")
    headers["x-uipath-tracebaggage"] = ",".join(baggage_parts)

    return headers
