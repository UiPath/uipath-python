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

    Filters out root/POST/GET spans and reparents their children for cleaner traces.

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
        # Track filtered spans for reparenting: span_id -> parent_span_id
        self._filtered_parents: dict[int, int | None] = {}

    def _upsert_span_async(
        self, span: Span | ReadableSpan, status_override: int | None = None
    ) -> None:
        """Run upsert_span in a background thread without blocking.

        Submits the upsert task to the thread pool and returns immediately.
        The thread pool handles execution with max_workers cap to prevent
        resource exhaustion.

        Handles reparenting: if span's parent was filtered (root/POST/GET),
        the span is reparented to its grandparent for cleaner trace hierarchy.
        """

        def _upsert():
            try:
                # Check if this span's parent was filtered
                parent_id_override = None
                if span.parent and span.parent.span_id in self._filtered_parents:
                    # Get the filtered parent's parent (grandparent)
                    grandparent_id = self._filtered_parents[span.parent.span_id]
                    if grandparent_id is not None:
                        # Convert to UUID string format for override
                        from uipath.tracing._utils import _SpanUtils

                        parent_id_override = str(
                            _SpanUtils.span_id_to_uuid4(grandparent_id)
                        )
                    else:
                        # Filtered parent had no parent, so this becomes a root span
                        parent_id_override = None

                # Call upsert with appropriate overrides
                self.exporter.upsert_span(
                    span,
                    status_override=status_override,
                    parent_id_override=parent_id_override,
                )
            except Exception as e:
                logger.debug(f"Failed to upsert span: {e}")

        # Submit to thread pool and return immediately (non-blocking)
        # The timeout parameter is reserved for shutdown operations
        self.executor.submit(_upsert)

    def on_start(
        self, span: Span, parent_context: context_api.Context | None = None
    ) -> None:
        """Called when span starts - upsert with RUNNING status (non-blocking)."""
        # Filter out root/POST/GET spans
        if span.name in ("root", "POST", "GET"):
            # Track filtered span's parent for reparenting
            parent_id = span.parent.span_id if span.parent else None
            self._filtered_parents[span.context.span_id] = parent_id
            return

        # Only track evaluation-related spans
        if span.attributes and self._is_eval_span(span):
            self._upsert_span_async(span, status_override=self.span_status.RUNNING)

    def on_end(self, span: ReadableSpan) -> None:
        """Called when span ends - upsert with final status (non-blocking)."""
        # Filter out root/POST/GET spans
        if span.name in ("root", "POST", "GET"):
            return

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
