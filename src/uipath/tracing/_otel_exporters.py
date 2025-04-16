import json
import logging
import os
from typing import Sequence

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

    def export(self, spans: Sequence[ReadableSpan]):
        """Export spans to UiPath LLM Ops."""
        logger.debug(
            f"Exporting {len(spans)} spans to {self.base_url}/llmopstenant_/api/Traces/spans"
        )

        span_list = [
            _SpanUtils.otel_span_to_uipath_span(span).to_dict() for span in spans
        ]

        trace_id = str(span_list[0]["TraceId"])
        url = f"{self.base_url}/llmopstenant_/api/Traces/spans?traceId={trace_id}&source=Robots"

        logger.debug("payload: ", json.dumps(span_list))

        res = self.http_client.post(url, json=span_list)

        if res.status_code == 200:
            return SpanExportResult.SUCCESS
        else:
            return SpanExportResult.FAILURE

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Force flush the exporter."""
        return True

    def _get_base_url(self) -> str:
        uipath_url = (
            os.environ.get("UIPATH_URL")
            or "https://cloud.uipath.com/dummyOrg/dummyTennant/"
        )

        uipath_url = uipath_url.rstrip("/")

        return uipath_url
