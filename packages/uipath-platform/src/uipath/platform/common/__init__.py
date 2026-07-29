"""UiPath Common Models.

This module contains common models used across multiple services.
"""

from typing import TYPE_CHECKING, Any

from uipath.core.triggers import UiPathResumeMetadata

# TODO: Remove the interrupt-model compatibility exports in the next breaking-change release.
if TYPE_CHECKING:
    from .interrupt_models import (
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

from ._api_client import ApiClient
from ._base_service import BaseService, resolve_trace_id
from ._bindings import (
    ConnectionResourceOverwrite,
    EntityResourceOverwrite,
    GenericResourceOverwrite,
    ResourceOverwrite,
    ResourceOverwriteParser,
    ResourceOverwritesContext,
    resource_override,
)
from ._config import UiPathApiConfig, UiPathConfig
from ._endpoints_manager import EndpointManager
from ._execution_context import ExecutionSourceContext, UiPathExecutionContext
from ._folder_context import FolderContext, header_folder
from ._http_config import get_ca_bundle_path, get_httpx_client_kwargs
from ._models import Endpoint, RequestSpec
from ._reference_context import (
    ReferenceContext,
    ReferenceContextAccessor,
    ReferenceEntry,
)
from ._service_url_overrides import inject_routing_headers, resolve_service_url
from ._span_utils import (
    ExecutionType,
    ReferenceHierarchySpanProcessor,
    SpanSource,
    SpanStatus,
    UiPathSpan,
    VerbosityLevel,
    _SpanUtils,
)
from ._url import UiPathUrl
from ._user_agent import user_agent_value
from .auth import TokenData
from .dynamic_schema import jsonschema_to_pydantic
from .paging import PagedResult
from .timeout import (
    UiPathTimeoutError,
    assert_no_timeout,
    get_resume_metadata,
    is_timeout,
)

__all__ = [
    "ApiClient",
    "BaseService",
    "UiPathApiConfig",
    "UiPathExecutionContext",
    "ExecutionSourceContext",
    "FolderContext",
    "TokenData",
    "UiPathConfig",
    "CreateTask",
    "CreateEscalation",
    "WaitEscalation",
    "InvokeProcess",
    "InvokeProcessRaw",
    "WaitTask",
    "WaitJob",
    "WaitJobRaw",
    "PagedResult",
    "CreateDeepRag",
    "CreateDeepRagRaw",
    "WaitDeepRag",
    "WaitDeepRagRaw",
    "CreateBatchTransform",
    "WaitBatchTransform",
    "DocumentExtraction",
    "WaitDocumentExtraction",
    "InvokeSystemAgent",
    "WaitSystemAgent",
    "CreateEphemeralIndex",
    "CreateEphemeralIndexRaw",
    "WaitEphemeralIndex",
    "WaitEphemeralIndexRaw",
    "DocumentExtractionValidation",
    "WaitDocumentExtractionValidation",
    "WaitIntegrationEvent",
    "WaitUntil",
    "RequestSpec",
    "Endpoint",
    "UiPathUrl",
    "user_agent_value",
    "get_ca_bundle_path",
    "get_httpx_client_kwargs",
    "resource_override",
    "header_folder",
    "validate_pagination_params",
    "EndpointManager",
    "jsonschema_to_pydantic",
    "ConnectionResourceOverwrite",
    "EntityResourceOverwrite",
    "ExecutionType",
    "GenericResourceOverwrite",
    "ResourceOverwrite",
    "ResourceOverwriteParser",
    "ResourceOverwritesContext",
    "ReferenceEntry",
    "ReferenceContext",
    "ReferenceContextAccessor",
    "ReferenceHierarchySpanProcessor",
    "SpanSource",
    "SpanStatus",
    "UiPathSpan",
    "VerbosityLevel",
    "_SpanUtils",
    "resolve_service_url",
    "inject_routing_headers",
    "resolve_trace_id",
    "UiPathTimeoutError",
    "UiPathResumeMetadata",
    "assert_no_timeout",
    "get_resume_metadata",
    "is_timeout",
]

from .validation import validate_pagination_params

_INTERRUPT_MODEL_NAMES = {
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
}


def __getattr__(name: str) -> Any:
    """Resolve moved interrupt models on demand."""
    if name not in _INTERRUPT_MODEL_NAMES:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    from . import interrupt_models

    value = interrupt_models._resolve(name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """List common exports, including compatibility aliases."""
    return sorted(set(globals()) | set(__all__))
