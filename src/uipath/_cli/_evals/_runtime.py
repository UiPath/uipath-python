import copy
from collections import defaultdict
from time import time
from typing import Dict, Generic, List, Optional, Sequence, TypeVar

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

from uipath.eval._helpers import auto_discover_entrypoint

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


class UiPathEvalContext(UiPathRuntimeContext, Generic[C]):
    """Context used for evaluation runs."""

    runtime_context: C
    no_report: bool
    workers: int
    eval_set: Optional[str] = None
    eval_ids: Optional[List[str]] = None

    def __init__(
        self,
        runtime_context: C,
        no_report: bool,
        workers: int,
        eval_set: Optional[str] = None,
        eval_ids: Optional[List[str]] = None,
        **kwargs,
    ):
        super().__init__(
            runtime_context=runtime_context,  # type: ignore
            no_report=no_report,
            workers=workers,
            eval_set=eval_set,
            eval_ids=eval_ids,
            **kwargs,
        )
        self._auto_discover()

    def _auto_discover(self):
        self.runtime_context.entrypoint = (
            self.runtime_context.entrypoint or auto_discover_entrypoint()
        )
        self.eval_set = self.eval_set or EvalHelpers.auto_discover_eval_set()


class UiPathEvalRuntime(UiPathBaseRuntime, Generic[T, C]):
    """Specialized runtime for evaluation runs, with access to the factory."""

    def __init__(
        self, context: "UiPathEvalContext[C]", factory: "UiPathRuntimeFactory[T, C]"
    ):
        super().__init__(context)
        self.context: "UiPathEvalContext[C]" = context
        self.factory: UiPathRuntimeFactory[T, C] = factory
        self.span_exporter: ExecutionSpanExporter = ExecutionSpanExporter()
        self.factory.add_span_exporter(self.span_exporter)

    @classmethod
    def from__eval_context(
        cls,
        context: "UiPathEvalContext[C]",
        factory: "UiPathRuntimeFactory[T, C]",
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
            execution_output_list.append(await self.execute_agent(eval_item))

        self.context.result = UiPathRuntimeResult(
            output={
                "results": execution_output_list,
            },
            status=UiPathRuntimeStatus.SUCCESSFUL,
            resume=None,
        )

        return self.context.runtime_context.result

    def _prepare_new_runtime_context(self, eval_item: EvaluationItem) -> C:
        runtime_context = copy.deepcopy(self.context.runtime_context)
        runtime_context.execution_id = eval_item.id
        runtime_context.input_json = eval_item.inputs
        # here we can pass other values from eval_item: expectedAgentBehavior, simulationInstructions etc.
        return runtime_context

    # TODO: this would most likely need to be ported to a public AgentEvaluator class
    async def execute_agent(
        self, eval_item: EvaluationItem
    ) -> "UiPathEvalRunExecutionOutput":
        runtime_context = self._prepare_new_runtime_context(eval_item)
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
