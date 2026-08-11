"""PiiDetection service for UiPath Platform.

Provides methods for detecting PII in documents and files.
"""

from uipath.core.tracing import traced

from ..common._base_service import BaseService
from ..common._config import UiPathApiConfig
from ..common._execution_context import UiPathExecutionContext
from ..common._models import Endpoint, RequestSpec
from .pii_detection import PiiDetectionRequest, PiiDetectionResponse

_PII_DETECTION_ENDPOINT = Endpoint("llmopstenant_/api/pii-detection")

# PII detection over documents/files can be slow, so override the default
# httpx client timeout (30s) with a longer per-request timeout.
_PII_DETECTION_TIMEOUT = 290.0


class PiiDetectionService(BaseService):
    """Service for detecting PII via UiPath."""

    def __init__(
        self,
        config: UiPathApiConfig,
        execution_context: UiPathExecutionContext,
    ) -> None:
        super().__init__(config=config, execution_context=execution_context)

    @traced(name="pii_detection_detect_pii", run_type="uipath")
    def detect_pii(self, request: PiiDetectionRequest) -> PiiDetectionResponse:
        """Detect PII in the provided documents and/or files.

        Args:
            request: The PII detection request payload.

        Returns:
            The PII detection response.
        """
        spec = self._pii_detection_spec(request)
        response = self.request(
            spec.method,
            url=spec.endpoint,
            json=spec.json,
            headers=spec.headers,
            scoped="tenant",
            timeout=_PII_DETECTION_TIMEOUT,
        )
        return PiiDetectionResponse.model_validate(response.json())

    @traced(name="pii_detection_detect_pii", run_type="uipath")
    async def detect_pii_async(
        self, request: PiiDetectionRequest
    ) -> PiiDetectionResponse:
        """Detect PII in the provided documents and/or files (async).

        Args:
            request: The PII detection request payload.

        Returns:
            The PII detection response.
        """
        spec = self._pii_detection_spec(request)
        response = await self.request_async(
            spec.method,
            url=spec.endpoint,
            json=spec.json,
            headers=spec.headers,
            scoped="tenant",
            timeout=_PII_DETECTION_TIMEOUT,
        )
        return PiiDetectionResponse.model_validate(response.json())

    def _pii_detection_spec(self, request: PiiDetectionRequest) -> RequestSpec:
        return RequestSpec(
            method="POST",
            endpoint=_PII_DETECTION_ENDPOINT,
            json=request.model_dump(by_alias=True, exclude_none=True),
        )
