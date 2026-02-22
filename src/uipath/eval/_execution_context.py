"""Execution context variables and span collection shared between eval.runtime and eval.mocks.

This is a leaf module with no internal dependencies (only opentelemetry),
so it can be safely imported from anywhere without triggering circular imports.
"""

from collections import defaultdict
from contextvars import ContextVar

from opentelemetry.sdk.trace import ReadableSpan, Span


class ExecutionSpanCollector:
    """Collects spans as they are created during execution."""

    def __init__(self):
        # { execution_id -> list of spans }
        self._spans: dict[str, list[ReadableSpan]] = defaultdict(list)

    def add_span(self, span: Span, execution_id: str) -> None:
        self._spans[execution_id].append(span)

    def get_spans(self, execution_id: str) -> list[ReadableSpan]:
        return self._spans.get(execution_id, [])

    def clear(self, execution_id: str | None = None) -> None:
        if execution_id:
            self._spans.pop(execution_id, None)
        else:
            self._spans.clear()


# Span collector for trace access during mocking
span_collector_context: ContextVar[ExecutionSpanCollector | None] = ContextVar(
    "span_collector", default=None
)

# Execution ID for the current evaluation item
execution_id_context: ContextVar[str | None] = ContextVar("execution_id", default=None)

# Evaluation set run ID (action ID) for grouping related LLM calls
eval_set_run_id_context: ContextVar[str | None] = ContextVar(
    "eval_set_run_id", default=None
)
