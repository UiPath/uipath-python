from collections import defaultdict
from time import time
from typing import Dict, Generic, List, Optional, Sequence, TypeVar

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

from .._runtime._contracts import (
    UiPathBaseRuntime,
    UiPathRuntimeContext,
    UiPathRuntimeFactory,
    UiPathRuntimeResult,
    UiPathRuntimeStatus,
)
from .._utils._eval_set import EvalHelpers
from ._models import EvaluationItem
from ._models._agent_execution_output import UiPathEvalRunExecutionOutput

T = TypeVar("T", bound=UiPathBaseRuntime)
C = TypeVar("C", bound=UiPathRuntimeContext)


class ExecutionSpanExporter(SpanExporter):
    """Custom exporter that stores spans grouped by execution ids."""

    def __init__(self):
        # { execution_id -> list of spans }
        self._spans: Dict[str, List[ReadableSpan]] = defaultdict(list)

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        for span in spans:
            if span.attributes is not None:
                exec_id = span.attributes.get("execution.id")
                if exec_id is not None and isinstance(exec_id, str):
                    self._spans[exec_id].append(span)

        return SpanExportResult.SUCCESS

    def get_spans(self, execution_id: str) -> List[ReadableSpan]:
        """Retrieve spans for a given execution id."""
        return self._spans.get(execution_id, [])

    def clear(self, execution_id: Optional[str] = None) -> None:
        """Clear stored spans for one or all executions."""
        if execution_id:
            self._spans.pop(execution_id, None)
        else:
            self._spans.clear()

    def shutdown(self) -> None:
        self.clear()


class UiPathEvalContext(UiPathRuntimeContext):
    """Context used for evaluation runs."""

    no_report: Optional[bool] = False
    workers: Optional[int] = 1
    eval_set: Optional[str] = None
    eval_ids: Optional[List[str]] = None


class UiPathEvalRuntime(UiPathBaseRuntime, Generic[T, C]):
    """Specialized runtime for evaluation runs, with access to the factory."""

    def __init__(self, context: UiPathEvalContext, factory: UiPathRuntimeFactory[T, C]):
        super().__init__(context)
        self.context: UiPathEvalContext = context
        self.factory: UiPathRuntimeFactory[T, C] = factory
        self.span_exporter: ExecutionSpanExporter = ExecutionSpanExporter()
        self.factory.add_span_exporter(self.span_exporter)

    @classmethod
    def from_eval_context(
        cls,
        context: UiPathEvalContext,
        factory: UiPathRuntimeFactory[T, C],
    ) -> "UiPathEvalRuntime[T, C]":
        return cls(context, factory)

    async def execute(self) -> Optional[UiPathRuntimeResult]:
        """Evaluation logic. Can spawn other runtimes through the factory."""
        if self.context.eval_set is None:
            raise ValueError("eval_set must be provided for evaluation runs")

        evaluation_set = EvalHelpers.load_eval_set(
            self.context.eval_set, self.context.eval_ids
        )
        execution_output_list: list[UiPathEvalRunExecutionOutput] = []
        for eval_item in evaluation_set.evaluations:
            execution_output = await self.execute_runtime(eval_item)
            execution_output_list.append(execution_output)

        self.context.result = UiPathRuntimeResult(
            output={
                "results": execution_output_list,
            },
            status=UiPathRuntimeStatus.SUCCESSFUL,
        )

        return self.context.result

    async def execute_runtime(
        self, eval_item: EvaluationItem
    ) -> UiPathEvalRunExecutionOutput:
        runtime_context: C = self.factory.new_context(
            execution_id=eval_item.id,
            input_json=eval_item.inputs,
            is_eval_run=True,
        )
        start_time = time()
        result = await self.factory.execute_in_root_span(
            runtime_context, root_span=eval_item.name
        )
        end_time = time()
        if runtime_context.execution_id is None:
            raise ValueError("execution_id must be set for eval runs")

        spans = self.span_exporter.get_spans(runtime_context.execution_id)
        self.span_exporter.clear(runtime_context.execution_id)

        if result is None:
            raise ValueError("Execution result cannot be None for eval runs")

        return UiPathEvalRunExecutionOutput(
            execution_time=end_time - start_time,
            spans=spans,
            result=result,
        )

    async def cleanup(self) -> None:
        """Cleanup runtime resources."""
        pass

    async def validate(self) -> None:
        """Cleanup runtime resources."""
        pass
