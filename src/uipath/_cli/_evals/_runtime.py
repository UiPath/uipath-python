from collections import defaultdict
from typing import Dict, Generic, List, Optional, TypeVar

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

from .._runtime._contracts import (
    UiPathBaseRuntime,
    UiPathRuntimeContext,
    UiPathRuntimeFactory,
    UiPathRuntimeResult,
)

T = TypeVar("T", bound=UiPathBaseRuntime)
C = TypeVar("C", bound=UiPathRuntimeContext)


class ExecutionSpanExporter(SpanExporter):
    """Custom exporter that stores spans grouped by execution ids."""

    def __init__(self):
        # { execution_id -> list of spans }
        self._spans: Dict[str, List[ReadableSpan]] = defaultdict(list)

    def export(self, spans: List[ReadableSpan]) -> SpanExportResult:
        for span in spans:
            exec_id = span.attributes.get("execution.id")
            if exec_id is not None:
                self._spans[exec_id].append(span)

        return SpanExportResult.SUCCESS

    def get_spans(self, execution_id: str) -> List[ReadableSpan]:
        """Retrieve spans for a given execution id."""
        return self._spans.get(execution_id, [])

    def clear(self, execution_id: str = None) -> None:
        """Clear stored spans for one or all executions."""
        if execution_id:
            self._spans.pop(execution_id, None)
        else:
            self._spans.clear()

    def shutdown(self) -> None:
        self.clear()


class UiPathEvalContext(UiPathRuntimeContext):
    """Context used for evaluation runs."""

    def __init__(self, evaluation_id: str, **kwargs):
        super().__init__(**kwargs)
        self.evaluation_id = evaluation_id


class UiPathEvalRuntime(UiPathBaseRuntime, Generic[T, C]):
    """Specialized runtime for evaluation runs, with access to the factory."""

    def __init__(
        self, context: UiPathEvalContext, factory: "UiPathRuntimeFactory[T, C]"
    ):
        super().__init__(context)
        self.context: UiPathEvalContext = context
        self.factory: UiPathRuntimeFactory[T, C] = factory
        self.span_exporter: ExecutionSpanExporter = ExecutionSpanExporter()
        self.factory.add_span_exporter(self.span_exporter)

    @classmethod
    def from_context(
        cls,
        context: UiPathEvalContext,
        factory: "UiPathRuntimeFactory[T, C]",
    ) -> "UiPathEvalRuntime[T, C]":
        return cls(context, factory)

    async def execute(self) -> Optional[UiPathRuntimeResult]:
        """Evaluation logic. Can spawn other runtimes through the factory."""
        runtime_context1 = self.factory.new_context(execution_id="child-exec-1")
        result1 = await self.factory.execute_in_root_span(runtime_context1)
        spans1 = self.span_exporter.get_spans("child-exec-1")
        self.span_exporter.clear("child-exec-1")

        runtime_context2 = self.factory.new_context(execution_id="child-exec-2")
        result2 = await self.factory.execute_in_root_span(runtime_context2)
        spans2 = self.span_exporter.get_spans("child-exec-2")

        return UiPathRuntimeResult(
            status="evaluated",
            data={
                "evaluation_id": self.context.evaluation_id,
            },
        )
