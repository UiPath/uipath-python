from collections import defaultdict
from typing import Dict, List, Optional

from opentelemetry.sdk.trace import ReadableSpan, Span


class ExecutionSpanCollector:
    """Collects spans as they are created during execution."""

    def __init__(self):
        # { execution_id -> list of spans }
        self._spans: Dict[str, List[ReadableSpan]] = defaultdict(list)

    def add_span(self, span: Span, execution_id: str) -> None:
        self._spans[execution_id].append(span)

    def get_spans(self, execution_id: str) -> List[ReadableSpan]:
        return self._spans.get(execution_id, [])

    def clear(self, execution_id: Optional[str] = None) -> None:
        if execution_id:
            self._spans.pop(execution_id, None)
        else:
            self._spans.clear()
