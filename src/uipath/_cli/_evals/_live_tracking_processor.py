import logging
from concurrent.futures import ThreadPoolExecutor

from opentelemetry import context as context_api
from opentelemetry.sdk.trace import ReadableSpan, Span, SpanProcessor

from uipath.tracing import LlmOpsHttpExporter, SpanStatus

logger = logging.getLogger(__name__)


class LiveTrackingSpanProcessor(SpanProcessor):
    """Span processor for live span tracking using upsert_span API.

    Sends real-time span updates:
    - On span start: Upsert with RUNNING status
    - On span end: Upsert with final status (OK/ERROR)

    All upsert calls run in background threads without blocking evaluation
    execution. Uses a thread pool to cap the maximum number of concurrent
    threads and avoid resource exhaustion.
    """

    def __init__(
        self,
        exporter: LlmOpsHttpExporter,
        max_workers: int = 10,
    ):
        self.exporter = exporter
        self.span_status = SpanStatus
        self.executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="span-upsert"
        )

    def _upsert_span_async(
        self, span: Span | ReadableSpan, status_override: int | None = None
    ) -> None:
        """Run upsert_span in a background thread without blocking.

        Submits the upsert task to the thread pool and returns immediately.
        The thread pool handles execution with max_workers cap to prevent
        resource exhaustion.
        """

        def _upsert():
            try:
                if status_override:
                    self.exporter.upsert_span(span, status_override=status_override)
                else:
                    self.exporter.upsert_span(span)
            except Exception as e:
                logger.debug(f"Failed to upsert span: {e}")

        # Submit to thread pool and return immediately (non-blocking)
        # The timeout parameter is reserved for shutdown operations
        self.executor.submit(_upsert)

    def on_start(
        self, span: Span, parent_context: context_api.Context | None = None
    ) -> None:
        """Called when span starts - upsert with RUNNING status (non-blocking)."""
        # Only track evaluation-related spans
        if span.attributes and self._is_eval_span(span):
            self._upsert_span_async(span, status_override=self.span_status.RUNNING)

    def on_end(self, span: ReadableSpan) -> None:
        """Called when span ends - upsert with final status (non-blocking)."""
        # Only track evaluation-related spans
        if span.attributes and self._is_eval_span(span):
            self._upsert_span_async(span)

    def _is_eval_span(self, span: Span | ReadableSpan) -> bool:
        """Check if span is evaluation-related."""
        if not span.attributes:
            return False

        span_type = span.attributes.get("span_type")
        # Track eval-related span types
        eval_span_types = {
            "eval",
            "evaluator",
            "evaluation",
            "eval_set_run",
            "evalOutput",
        }

        if span_type in eval_span_types:
            return True

        # Also track spans with execution.id (eval executions)
        if "execution.id" in span.attributes:
            return True

        return False

    def shutdown(self) -> None:
        """Shutdown the processor and wait for pending tasks to complete."""
        try:
            self.executor.shutdown(wait=True)
        except Exception as e:
            logger.debug(f"Executor shutdown failed: {e}")

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Force flush - no-op for live tracking."""
        return True
