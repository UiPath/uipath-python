"""Tracing utilities and OpenTelemetry exporters."""

from uipath.core import traced
from uipath.platform.common._reference_context import (
    ReferenceContext,
    ReferenceContextAccessor,
    ReferenceEntry,
)
from uipath.platform.common._span_utils import (
    AttachmentDirection,
    AttachmentProvider,
    SpanAttachment,
    SpanStatus,
    VerbosityLevel,
)

from ._live_tracking_processor import LiveTrackingSpanProcessor
from ._otel_exporters import (  # noqa: D104
    JsonLinesFileExporter,
    LlmOpsHttpExporter,
)

__all__ = [
    "traced",
    "LlmOpsHttpExporter",
    "JsonLinesFileExporter",
    "LiveTrackingSpanProcessor",
    "SpanStatus",
    "AttachmentDirection",
    "AttachmentProvider",
    "SpanAttachment",
    "VerbosityLevel",
    "ReferenceEntry",
    "ReferenceContext",
    "ReferenceContextAccessor",
]
