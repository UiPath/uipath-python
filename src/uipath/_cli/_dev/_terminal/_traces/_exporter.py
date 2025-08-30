import logging
from datetime import datetime
from typing import Callable, Sequence

from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from opentelemetry.trace import Span, StatusCode

from .._models._messages import LogMessage, TraceMessage


class RunContextExporter(SpanExporter):
    """Custom trace exporter that sends traces and logs to CLI UI."""

    def __init__(
        self,
        run_id: str,
        on_trace: Callable[[TraceMessage], None],
        on_log: Callable[[LogMessage], None],
    ):
        self.run_id = run_id
        self.on_trace = on_trace
        self.on_log = on_log
        self.logger = logging.getLogger(__name__)

    def export(self, spans: Sequence[Span]) -> SpanExportResult:
        """Export spans to CLI UI."""
        try:
            for span in spans:
                self._export_span(span)
            return SpanExportResult.SUCCESS
        except Exception as e:
            self.logger.error(f"Failed to export spans: {e}")
            return SpanExportResult.FAILURE

    def _export_span(self, span: Span):
        """Export a single span to CLI UI."""
        # Calculate duration
        start_time = span.start_time / 1_000_000_000  # Convert to seconds
        end_time = span.end_time / 1_000_000_000 if span.end_time else None
        duration_ms = (end_time - start_time) * 1000 if end_time else None

        # Determine status
        if span.status.status_code == StatusCode.ERROR:
            status = "failed"
        elif end_time:
            status = "completed"
        else:
            status = "running"

        # Extract span context information
        span_context = span.get_span_context()

        # Convert span IDs to string format (they're usually int64)
        span_id = f"{span_context.span_id:016x}"  # 16-char hex string
        trace_id = f"{span_context.trace_id:032x}"  # 32-char hex string

        # Get parent span ID if available
        parent_span_id = None
        if hasattr(span, "parent") and span.parent:
            parent_span_id = f"{span.parent.span_id:016x}"

        # Create trace message with all required fields
        trace_msg = TraceMessage(
            run_id=self.run_id,
            span_name=span.name,
            span_id=span_id,
            parent_span_id=parent_span_id,
            trace_id=trace_id,
            status=status,
            duration_ms=duration_ms,
            timestamp=datetime.fromtimestamp(start_time),
            attributes=dict(span.attributes) if span.attributes else {},
        )

        # Send to UI
        self.on_trace(trace_msg)

        # Also send logs if there are events
        if hasattr(span, "events") and span.events:
            for event in span.events:
                log_level = self._determine_log_level(event, span.status)
                log_msg = LogMessage(
                    run_id=self.run_id,
                    level=log_level,
                    message=event.name,
                    timestamp=datetime.fromtimestamp(event.timestamp / 1_000_000_000),
                )
                self.on_log(log_msg)

    def _determine_log_level(self, event, span_status) -> str:
        """Determine log level from span event."""
        event_name = event.name.lower()

        if span_status.status_code == StatusCode.ERROR:
            return "ERROR"
        elif "error" in event_name or "exception" in event_name:
            return "ERROR"
        elif "warn" in event_name:
            return "WARNING"
        elif "debug" in event_name:
            return "DEBUG"
        else:
            return "INFO"

    def shutdown(self) -> None:
        """Shutdown the exporter."""
        pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Force flush any pending spans."""
        return True
