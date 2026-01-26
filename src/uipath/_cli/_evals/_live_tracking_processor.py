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

    All upsert calls run in background threads without blocking execution.
    Uses a thread pool to cap the maximum number of concurrent threads
    and avoid resource exhaustion.

    Filtering:
        Applies the span_filter from factory settings (if provided).
        - Low-code agents: Filter to uipath.custom_instrumentation=True
        - Coded functions: No filtering (settings=None)

    Architecture note:
        One LiveTrackingSpanProcessor per LlmOpsHttpExporter.
        Do not share processors between exporters.
    """

    def __init__(
        self,
        exporter: LlmOpsHttpExporter,
        max_workers: int = 10,
        settings=None,
    ):
        self.exporter = exporter
        self.span_status = SpanStatus
        self.settings = settings
        self.span_filter = (
            settings.trace_settings.span_filter
            if settings and settings.trace_settings
            else None
        )
        self.executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="span-upsert"
        )

    @classmethod
    def create_and_register(
        cls,
        exporter: LlmOpsHttpExporter,
        trace_manager,
        max_workers: int = 10,
        settings=None,
    ) -> "LiveTrackingSpanProcessor":
        """Factory method to create and register a live tracking processor.

        Creates one LiveTrackingSpanProcessor per exporter following the
        architecture pattern: one processor → one exporter.

        Args:
            exporter: The LlmOpsHttpExporter to send upserts to
            trace_manager: UiPathTraceManager instance to register with
            max_workers: Thread pool size for async upserts
            settings: UiPathRuntimeFactorySettings with optional span_filter

        Returns:
            The created and registered processor
        """
        processor = cls(exporter, max_workers, settings)
        trace_manager.add_span_processor(processor)
        return processor

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
        # Apply factory span filter if configured
        if self.span_filter is None or self.span_filter(span):
            self._upsert_span_async(span, status_override=self.span_status.RUNNING)

    def on_end(self, span: ReadableSpan) -> None:
        """Called when span ends - upsert with final status (non-blocking)."""
        # Apply factory span filter if configured
        if self.span_filter is None or self.span_filter(span):
            self._upsert_span_async(span)

    def shutdown(self) -> None:
        """Shutdown the processor and wait for pending tasks to complete."""
        try:
            self.executor.shutdown(wait=True)
        except Exception as e:
            logger.debug(f"Executor shutdown failed: {e}")

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Force flush - no-op for live tracking."""
        return True
