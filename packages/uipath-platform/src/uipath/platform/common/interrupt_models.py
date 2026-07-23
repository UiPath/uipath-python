"""Deprecated lazy aliases for resume trigger interrupt models."""

import warnings
from typing import TYPE_CHECKING, Any

# TODO: Remove this compatibility module in the next breaking-change release.
if TYPE_CHECKING:
    from uipath.platform.resume_triggers.interrupt_models import (
        CreateBatchTransform,
        CreateDeepRag,
        CreateDeepRagRaw,
        CreateEphemeralIndex,
        CreateEphemeralIndexRaw,
        CreateEscalation,
        CreateTask,
        DocumentExtraction,
        DocumentExtractionValidation,
        InvokeProcess,
        InvokeProcessRaw,
        InvokeSystemAgent,
        WaitBatchTransform,
        WaitDeepRag,
        WaitDeepRagRaw,
        WaitDocumentExtraction,
        WaitDocumentExtractionValidation,
        WaitEphemeralIndex,
        WaitEphemeralIndexRaw,
        WaitEscalation,
        WaitIntegrationEvent,
        WaitJob,
        WaitJobRaw,
        WaitSystemAgent,
        WaitTask,
        WaitUntil,
    )

__all__ = [
    "CreateBatchTransform",
    "CreateDeepRag",
    "CreateDeepRagRaw",
    "CreateEphemeralIndex",
    "CreateEphemeralIndexRaw",
    "CreateEscalation",
    "CreateTask",
    "DocumentExtraction",
    "DocumentExtractionValidation",
    "InvokeProcess",
    "InvokeProcessRaw",
    "InvokeSystemAgent",
    "WaitBatchTransform",
    "WaitDeepRag",
    "WaitDeepRagRaw",
    "WaitDocumentExtraction",
    "WaitDocumentExtractionValidation",
    "WaitEphemeralIndex",
    "WaitEphemeralIndexRaw",
    "WaitEscalation",
    "WaitIntegrationEvent",
    "WaitJob",
    "WaitJobRaw",
    "WaitSystemAgent",
    "WaitTask",
    "WaitUntil",
]


def _resolve(name: str) -> Any:
    """Resolve a deprecated alias from the canonical module and warn.

    Called only from a module ``__getattr__`` (here or in ``common``), so the
    frame three levels up from ``warnings.warn`` is the user's import site.
    """
    import uipath.platform.resume_triggers.interrupt_models as canonical_models

    value = getattr(canonical_models, name)
    warnings.warn(
        "Importing interrupt models from uipath.platform.common is deprecated "
        "and will be removed in a future release; import from "
        "uipath.platform.resume_triggers instead.",
        DeprecationWarning,
        stacklevel=3,
    )
    globals()[name] = value
    return value


def __getattr__(name: str) -> Any:
    """Resolve deprecated interrupt model aliases on demand."""
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return _resolve(name)


def __dir__() -> list[str]:
    """List compatibility exports."""
    return sorted(set(globals()) | set(__all__))
