import json
import logging
import os
import time
from typing import Any, Dict, Sequence

from httpx import Client
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import (
    SpanExporter,
    SpanExportResult,
)

from ._utils import _SpanUtils

logger = logging.getLogger(__name__)


class LlmOpsHttpExporter(SpanExporter):
    """An OpenTelemetry span exporter that sends spans to UiPath LLM Ops."""

    def __init__(self, **kwargs):
        """Initialize the exporter with the base URL and authentication token."""
        super().__init__(**kwargs)
        self.base_url = self._get_base_url()
        self.auth_token = os.environ.get("UIPATH_ACCESS_TOKEN")
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.auth_token}",
        }

        self.http_client = Client(headers=self.headers)

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        """Export spans to UiPath LLM Ops."""
        logger.debug(
            f"Exporting {len(spans)} spans to {self.base_url}/llmopstenant_/api/Traces/spans"
        )

        span_list = [
            _SpanUtils.otel_span_to_uipath_span(span).to_dict() for span in spans
        ]
        url = self._build_url(span_list)

        logger.debug("Payload: %s", json.dumps(span_list))

        return self._send_with_retries(url, span_list)

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Force flush the exporter."""
        return True

    def _build_url(self, span_list: list[Dict[str, Any]]) -> str:
        """Construct the URL for the API request."""
        trace_id = str(span_list[0]["TraceId"])
        return f"{self.base_url}/llmopstenant_/api/Traces/spans?traceId={trace_id}&source=Robots"

    def _send_with_retries(
        self, url: str, payload: list[Dict[str, Any]], max_retries: int = 4
    ) -> SpanExportResult:
        """Send the HTTP request with retry logic."""
        for attempt in range(max_retries):
            try:
                response = self.http_client.post(url, json=payload)
                if response.status_code == 200:
                    return SpanExportResult.SUCCESS
                else:
                    logger.warning(
                        f"Attempt {attempt + 1} failed with status code {response.status_code}: {response.text}"
                    )
            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed with exception: {e}")

            if attempt < max_retries - 1:
                time.sleep(1.5**attempt)  # Exponential backoff

        return SpanExportResult.FAILURE

    def _get_base_url(self) -> str:
        uipath_url = (
            os.environ.get("UIPATH_URL")
            or "https://cloud.uipath.com/dummyOrg/dummyTennant/"
        )

        uipath_url = uipath_url.rstrip("/")

        return uipath_url
