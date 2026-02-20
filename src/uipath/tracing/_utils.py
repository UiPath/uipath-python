"""Re-export from uipath.platform.common for backward compatibility."""

from uipath.platform.common._span_utils import (
    AttachmentDirection,
    AttachmentProvider,
    SpanAttachment,
    UiPathSpan,
    _SpanUtils,
)

__all__ = [
    "AttachmentDirection",
    "AttachmentProvider",
    "SpanAttachment",
    "UiPathSpan",
    "_SpanUtils",
]
