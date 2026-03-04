"""OpenTelemetry tracing module with UiPath integration.

This module provides decorators and utilities for instrumenting Python functions
with OpenTelemetry tracing, including custom processors for UiPath execution tracking.
"""

from uipath.core.tracing.decorators import traced
from uipath.core.tracing.span_utils import UiPathSpanUtils
from uipath.core.tracing.trace_manager import UiPathTraceManager
from uipath.core.tracing.types import UiPathTraceSettings

__all__ = [
    "traced",
    "UiPathSpanUtils",
    "UiPathTraceManager",
    "UiPathTraceSettings",
]
