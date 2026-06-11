"""Shared helpers for StudioWeb evaluation reporting."""

import functools
import json
import logging
import os
import uuid
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)


def gracefully_handle_errors(func):
    """Decorator to catch and log errors without stopping execution."""

    @functools.wraps(func)
    async def wrapper(self, *args, **kwargs):
        try:
            return await func(self, *args, **kwargs)
        except Exception as e:
            if hasattr(self, "_console"):
                error_type = type(e).__name__
                # Log the full error message for debugging
                logger.debug(f"Full error details: {e}")
                logger.warning(
                    f"Cannot report progress to SW. "
                    f"Function: {func.__name__}, "
                    f"Error type: {error_type}, "
                    f"Details: {e}"
                )
            return None

    return wrapper


def to_deterministic_guid(id_value: str) -> str:
    """Return ``id_value`` if it already is a GUID, else a deterministic uuid5.

    The legacy backend APIs require GUID identifiers; coded eval sets may use
    arbitrary string IDs, which are mapped to a stable GUID.
    """
    try:
        uuid.UUID(id_value)
        return id_value
    except ValueError:
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, id_value))


def serialize_justification(justification: BaseModel | str | None) -> str | None:
    """Serialize justification to JSON string for API compatibility.

    Args:
        justification: The justification object which could be None, a BaseModel,
                      a string, or any other JSON-serializable object

    Returns:
        JSON string representation or None if justification is None
    """
    if isinstance(justification, BaseModel):
        justification = json.dumps(justification.model_dump())

    return justification


def resolve_project_files_source() -> int | None:
    """Map UIPATH_PROJECT_FILES_SOURCE (Local/Cloud) to the backend enum int."""
    raw = os.getenv("UIPATH_PROJECT_FILES_SOURCE")
    if not raw:
        return None
    normalized = raw.strip().lower()
    if normalized == "local":
        return 1
    if normalized == "cloud":
        return 0
    try:
        return int(normalized)
    except ValueError:
        logger.warning(
            f"Unrecognized UIPATH_PROJECT_FILES_SOURCE value: {raw!r}; ignoring."
        )
        return None


def extract_usage_from_spans(spans: list[Any]) -> dict[str, int | float | None]:
    """Extract token usage and cost from OpenTelemetry spans.

    Args:
        spans: List of ReadableSpan objects from agent execution

    Returns:
        Dictionary with tokens, completionTokens, promptTokens, and cost
    """
    total_tokens = 0
    completion_tokens = 0
    prompt_tokens = 0
    total_cost = 0.0

    for span in spans:
        try:
            # Handle both dictionary attributes and string Attributes field
            attrs = None
            if hasattr(span, "attributes") and span.attributes:
                if isinstance(span.attributes, dict):
                    attrs = span.attributes
                elif isinstance(span.attributes, str):
                    # Parse JSON string attributes
                    attrs = json.loads(span.attributes)

            # Also check for Attributes field (capitalized) from backend spans
            if not attrs and hasattr(span, "Attributes") and span.Attributes:
                if isinstance(span.Attributes, str):
                    attrs = json.loads(span.Attributes)
                elif isinstance(span.Attributes, dict):
                    attrs = span.Attributes

            if attrs:
                # Try to get usage from nested usage object (backend format)
                if "usage" in attrs and isinstance(attrs["usage"], dict):
                    usage = attrs["usage"]
                    prompt_tokens += usage.get("promptTokens", 0)
                    completion_tokens += usage.get("completionTokens", 0)
                    total_tokens += usage.get("totalTokens", 0)
                    # Cost might be in usage or at root level
                    total_cost += usage.get("cost", 0.0)

                # Also try OpenTelemetry semantic conventions (SDK format)
                prompt_tokens += attrs.get("gen_ai.usage.prompt_tokens", 0)
                completion_tokens += attrs.get("gen_ai.usage.completion_tokens", 0)
                total_tokens += attrs.get("gen_ai.usage.total_tokens", 0)
                total_cost += attrs.get("gen_ai.usage.cost", 0.0)
                total_cost += attrs.get("llm.usage.cost", 0.0)

        except (json.JSONDecodeError, AttributeError, TypeError) as e:
            logger.debug(f"Failed to parse span attributes: {e}")
            continue

    return {
        "tokens": total_tokens if total_tokens > 0 else None,
        "completionTokens": completion_tokens if completion_tokens > 0 else None,
        "promptTokens": prompt_tokens if prompt_tokens > 0 else None,
        "cost": total_cost if total_cost > 0 else None,
    }
