"""PiiDetection service package.

Provides the ``PiiDetectionService`` client, Pydantic request/response models for
the PII detection endpoint, and utilities for rehydrating masked text with
original PII values after LLM processing.
"""

from ._pii_detection_service import PiiDetectionService
from .pii_detection import (
    PiiDetectionRequest,
    PiiDetectionResponse,
    PiiDocument,
    PiiDocumentResult,
    PiiEntity,
    PiiEntityThreshold,
    PiiFile,
    PiiFileResult,
)
from .pii_utilities import (
    rehydrate_from_pii_entities,
    rehydrate_from_pii_response,
)

__all__ = [
    "PiiDetectionRequest",
    "PiiDetectionResponse",
    "PiiDetectionService",
    "PiiDocument",
    "PiiDocumentResult",
    "PiiEntity",
    "PiiEntityThreshold",
    "PiiFile",
    "PiiFileResult",
    "rehydrate_from_pii_entities",
    "rehydrate_from_pii_response",
]
