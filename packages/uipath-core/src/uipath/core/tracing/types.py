"""Tracing types for UiPath SDK."""

from typing import Callable

from opentelemetry.sdk.trace import ReadableSpan
from pydantic import BaseModel, Field


class UiPathTraceSettings(BaseModel):
    """Trace settings for UiPath SDK."""

    model_config = {"arbitrary_types_allowed": True}  # Needed for Callable

    span_filter: Callable[[ReadableSpan], bool] | None = Field(
        default=None,
        description=(
            "Optional filter to decide whether a span should be exported. "
            "Called when a span ends with a ReadableSpan argument. "
            "Return True to export, False to skip."
        ),
    )
