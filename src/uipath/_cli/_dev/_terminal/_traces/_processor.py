from typing import Optional

from opentelemetry import context as context_api
from opentelemetry import trace
from opentelemetry.sdk.trace import ReadableSpan, Span, SpanProcessor
from opentelemetry.sdk.trace.export import SpanExporter


class RunContextProcessor(SpanProcessor):
    def __init__(self):
        self._exporters: dict[str, SpanExporter] = {}

    def register_exporter(self, run_id: str, exporter: SpanExporter):
        self._exporters[run_id] = exporter

    def unregister_exporter(self, run_id: str):
        exporter = self._exporters.pop(run_id, None)
        if exporter:
            exporter.force_flush()
            exporter.shutdown()

    def on_start(
        self, span: Span, parent_context: Optional[context_api.Context] = None
    ):
        parent_span = trace.get_current_span()
        if parent_span and parent_span.is_recording():
            run_id = parent_span.attributes.get("run.id")
            if run_id:
                span.set_attribute("run.id", run_id)

    def on_end(self, span: ReadableSpan):
        run_id = span.attributes.get("run.id")
        if run_id and run_id in self._exporters:
            self._exporters[run_id].export([span])

    def shutdown(self):
        for exporter in self._exporters.values():
            exporter.shutdown()
        self._exporters.clear()
