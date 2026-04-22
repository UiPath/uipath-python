"""SemanticProxy service for UiPath Platform.

Provides methods for interacting with the SemanticProxy service (e.g. PII detection).
"""

from uipath.core.tracing import traced

from ..common._base_service import BaseService
from ..common._config import UiPathApiConfig
from ..common._execution_context import UiPathExecutionContext
from ..common._models import Endpoint, RequestSpec
from .semantic_proxy import PiiDetectionRequest, PiiDetectionResponse

_PII_DETECTION_ENDPOINT = Endpoint("semanticproxy_/api/pii-detection")


class SemanticProxyService(BaseService):
    """Service for interacting with UiPath SemanticProxy."""

    def __init__(
        self,
        config: UiPathApiConfig,
        execution_context: UiPathExecutionContext,
    ) -> None:
        super().__init__(config=config, execution_context=execution_context)

    @traced(name="semantic_proxy_detect_pii", run_type="uipath")
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
        )
        return PiiDetectionResponse.model_validate(response.json())

    @traced(name="semantic_proxy_detect_pii", run_type="uipath")
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
        )
        return PiiDetectionResponse.model_validate(response.json())

    def _pii_detection_spec(self, request: PiiDetectionRequest) -> RequestSpec:
        return RequestSpec(
            method="POST",
            endpoint=_PII_DETECTION_ENDPOINT,
            json=request.model_dump(by_alias=True, exclude_none=True),
        )
