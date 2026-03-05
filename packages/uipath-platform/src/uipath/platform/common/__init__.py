"""UiPath Common Models.

This module contains common models used across multiple services.
"""

from ._api_client import ApiClient
from ._base_service import BaseService
from ._bindings import (
    ConnectionResourceOverwrite,
    GenericResourceOverwrite,
    ResourceOverwrite,
    ResourceOverwriteParser,
    ResourceOverwritesContext,
    resource_override,
)
from ._config import UiPathApiConfig, UiPathConfig
from ._endpoints_manager import EndpointManager
from ._execution_context import UiPathExecutionContext
from ._external_application_service import ExternalApplicationService
from ._folder_context import FolderContext, header_folder
from ._http_config import get_httpx_client_kwargs
from ._models import Endpoint, RequestSpec
from ._service_url_overrides import inject_routing_headers, resolve_service_url
from ._span_utils import UiPathSpan, _SpanUtils
from ._url import UiPathUrl
from ._user_agent import user_agent_value
from .auth import TokenData
from .dynamic_schema import jsonschema_to_pydantic
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
    WaitJob,
    WaitJobRaw,
    WaitSystemAgent,
    WaitTask,
)
from .paging import PagedResult

__all__ = [
    "ApiClient",
    "BaseService",
    "UiPathApiConfig",
    "UiPathExecutionContext",
    "ExternalApplicationService",
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
    "RequestSpec",
    "Endpoint",
    "UiPathUrl",
    "user_agent_value",
    "get_httpx_client_kwargs",
    "resource_override",
    "header_folder",
    "validate_pagination_params",
    "EndpointManager",
    "jsonschema_to_pydantic",
    "ConnectionResourceOverwrite",
    "GenericResourceOverwrite",
    "ResourceOverwrite",
    "ResourceOverwriteParser",
    "ResourceOverwritesContext",
    "UiPathSpan",
    "_SpanUtils",
    "resolve_service_url",
    "inject_routing_headers",
]

from .validation import validate_pagination_params
