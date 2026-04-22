"""SemanticProxy service package.

Provides the ``SemanticProxyService`` client, Pydantic request/response models for
the PII detection endpoint, and utilities for rehydrating masked text with
original PII values after LLM processing.
"""

from ._semantic_proxy_service import SemanticProxyService
from .pii_utilities import (
    rehydrate_from_pii_entities,
    rehydrate_from_pii_response,
)
from .semantic_proxy import (
    PiiDetectionRequest,
    PiiDetectionResponse,
    PiiDocument,
    PiiDocumentResult,
    PiiEntity,
    PiiEntityThreshold,
    PiiFile,
    PiiFileResult,
)

__all__ = [
    "PiiDetectionRequest",
    "PiiDetectionResponse",
    "PiiDocument",
    "PiiDocumentResult",
    "PiiEntity",
    "PiiEntityThreshold",
    "PiiFile",
    "PiiFileResult",
    "SemanticProxyService",
    "rehydrate_from_pii_entities",
    "rehydrate_from_pii_response",
]
