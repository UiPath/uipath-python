import asyncio
import json
import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from time import time
from typing import Any, Dict, Generic, List, Optional, Sequence, TypeVar

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

from ..._events._event_bus import EventBus
from ..._events._events import (
    BatchProgressEvent,
    EvalProgressEvent,
    EvalRunCreatedEvent,
    EvalRunUpdatedEvent,
    EvalSetRunCreatedEvent,
    EvalSetRunUpdatedEvent,
    EvaluationEvents,
)
from ...eval.evaluators import BaseEvaluator
from ...eval.models import EvaluationResult
from ...eval.models.models import AgentExecution, EvalItemResult
from .._runtime._contracts import (
    UiPathBaseRuntime,
    UiPathRuntimeContext,
    UiPathRuntimeFactory,
    UiPathRuntimeResult,
    UiPathRuntimeStatus,
)
from .._runtime._logging import ExecutionLogHandler
from .._utils._eval_set import EvalHelpers
from ._evaluator_factory import EvaluatorFactory
from ._models._evaluation_set import EvaluationItem, EvaluationSet
from ._models._output import (
    EvaluationResultDto,
    EvaluationRunResult,
    EvaluationRunResultDto,
    UiPathEvalOutput,
    UiPathEvalRunExecutionOutput,
)
from .mocks.mocks import set_evaluation_item

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


class ExecutionLogsExporter:
    """Custom exporter that stores multiple execution log handlers."""

    def __init__(self):
        self._log_handlers: dict[str, ExecutionLogHandler] = {}

    def register(self, execution_id: str, handler: ExecutionLogHandler) -> None:
        self._log_handlers[execution_id] = handler

    def get_logs(self, execution_id: str) -> list[logging.LogRecord]:
        """Clear stored spans for one or all executions."""
        log_handler = self._log_handlers.get(execution_id)
        return log_handler.buffer if log_handler else []

    def clear(self, execution_id: Optional[str] = None) -> None:
        """Clear stored spans for one or all executions."""
        if execution_id:
            self._log_handlers.pop(execution_id, None)
        else:
            self._log_handlers.clear()

    def flush_logs(self, execution_id: str, target_handler: logging.Handler) -> None:
        log_handler = self._log_handlers.get(execution_id)
        if log_handler:
            log_handler.flush_execution_logs(target_handler)


class UiPathEvalContext(UiPathRuntimeContext):
    """Context used for evaluation runs."""

    no_report: Optional[bool] = False
    workers: Optional[int] = 1
    eval_set: Optional[str] = None
    eval_ids: Optional[List[str]] = None


class UiPathEvalRuntime(UiPathBaseRuntime, Generic[T, C]):
    """Specialized runtime for evaluation runs, with access to the factory."""

    def __init__(
        self,
        context: UiPathEvalContext,
        factory: UiPathRuntimeFactory[T, C],
        event_bus: EventBus,
    ):
        super().__init__(context)
        self.context: UiPathEvalContext = context
        self.factory: UiPathRuntimeFactory[T, C] = factory
        self.event_bus: EventBus = event_bus
        self.span_exporter: ExecutionSpanExporter = ExecutionSpanExporter()
        self.factory.add_span_exporter(self.span_exporter)
        self.logs_exporter: ExecutionLogsExporter = ExecutionLogsExporter()
        self.execution_id = str(uuid.uuid4())

    @classmethod
    def from_eval_context(
        cls,
        context: UiPathEvalContext,
        factory: UiPathRuntimeFactory[T, C],
        event_bus: EventBus,
    ) -> "UiPathEvalRuntime[T, C]":
        return cls(context, factory, event_bus)

    async def execute(self) -> Optional[UiPathRuntimeResult]:
        if self.context.eval_set is None:
            raise ValueError("eval_set must be provided for evaluation runs")

        event_bus = self.event_bus

        evaluation_set = EvalHelpers.load_eval_set(
            self.context.eval_set, self.context.eval_ids
        )
        evaluators = self._load_evaluators(evaluation_set)

        await event_bus.publish(
            EvaluationEvents.CREATE_EVAL_SET_RUN,
            EvalSetRunCreatedEvent(
                execution_id=self.execution_id,
                entrypoint=self.context.entrypoint or "",
                eval_set_id=evaluation_set.id,
                no_of_evals=len(evaluation_set.evaluations),
                evaluators=evaluators,
            ),
        )

        workers = self.context.workers
        total_evaluations = len(evaluation_set.evaluations)

        # Calculate optimal batch size: ceil(evaluations / workers)
        batch_size = max(1, (total_evaluations + workers - 1) // workers)

        # Check if parallel execution should be used
        if workers > 1 and len(evaluation_set.evaluations) > 1:
            executor = ParallelEvalExecutor(
                max_workers=workers,
                batch_size=batch_size,
                factory=self.factory,
                event_bus=event_bus,
                context=self.context,
                evaluators=evaluators,
                span_exporter=self.span_exporter,
            )

            results = await executor.execute_parallel(evaluation_set)
        else:
            results = await self._execute_sequential(evaluation_set, evaluators)

        evaluator_averages = self._calculate_evaluator_averages(results, evaluators)

        await event_bus.publish(
            EvaluationEvents.UPDATE_EVAL_SET_RUN,
            EvalSetRunUpdatedEvent(
                execution_id=self.context.execution_id,
                evaluator_scores=evaluator_averages,
            ),
            wait_for_completion=False,
        )

        self.context.result = UiPathRuntimeResult(
            output={**results.model_dump(by_alias=True)},
            status=UiPathRuntimeStatus.SUCCESSFUL,
        )
        return self.context.result

    async def _execute_sequential(
        self, evaluation_set: EvaluationSet, evaluators: List[BaseEvaluator[Any]]
    ) -> UiPathEvalOutput:
        """Execute evaluations sequentially (original behavior)."""
        evaluator_averages = {evaluator.id: 0.0 for evaluator in evaluators}
        evaluator_counts = {evaluator.id: 0 for evaluator in evaluators}

        results = UiPathEvalOutput(
            evaluation_set_name=evaluation_set.name, score=0, evaluation_set_results=[]
        )

        for eval_item in evaluation_set.evaluations:
            set_evaluation_item(eval_item)
            await event_bus.publish(
                EvaluationEvents.CREATE_EVAL_RUN,
                EvalRunCreatedEvent(
                    execution_id=self.execution_id,
                    eval_item=eval_item,
                ),
            )

            evaluation_run_results = EvaluationRunResult(
                evaluation_name=eval_item.name, evaluation_run_results=[]
            )

            results.evaluation_set_results.append(evaluation_run_results)

            try:
                agent_execution_output = await self.execute_runtime(eval_item)
                evaluation_item_results: list[EvalItemResult] = []

                for evaluator in evaluators:
                    evaluation_result = await self.run_evaluator(
                        evaluator=evaluator,
                        execution_output=agent_execution_output,
                        eval_item=eval_item,
                    )

                    dto_result = EvaluationResultDto.from_evaluation_result(
                        evaluation_result
                    )
                    evaluator_counts[evaluator.id] += 1
                    count = evaluator_counts[evaluator.id]
                    evaluator_averages[evaluator.id] += (
                        dto_result.score - evaluator_averages[evaluator.id]
                    ) / count

                    evaluation_run_results.evaluation_run_results.append(
                        EvaluationRunResultDto(
                            evaluator_name=evaluator.name,
                            result=dto_result,
                        )
                    )
                    evaluation_item_results.append(
                        EvalItemResult(
                            evaluator_id=evaluator.id,
                            result=evaluation_result,
                        )
                    )

                evaluation_run_results.compute_average_score()

                await self.event_bus.publish(
                    EvaluationEvents.UPDATE_EVAL_RUN,
                    EvalRunUpdatedEvent(
                        execution_id=self.execution_id,
                        eval_item=eval_item,
                        eval_results=evaluation_item_results,
                        success=not agent_execution_output.result.error,
                        agent_output=agent_execution_output.result.output,
                        agent_execution_time=agent_execution_output.execution_time,
                        spans=agent_execution_output.spans,
                        logs=agent_execution_output.logs,
                    ),
                    wait_for_completion=False,
                )
            except Exception as e:
                error_msg = str(e)
                eval_item._error_message = error_msg  # type: ignore[attr-defined]

                for evaluator in evaluators:
                    evaluator_counts[evaluator.id] += 1
                    count = evaluator_counts[evaluator.id]
                    evaluator_averages[evaluator.id] += (
                        0.0 - evaluator_averages[evaluator.id]
                    ) / count

                await self.event_bus.publish(
                    EvaluationEvents.UPDATE_EVAL_RUN,
                    EvalRunUpdatedEvent(
                        execution_id=self.execution_id,
                        eval_item=eval_item,
                        eval_results=[],
                        success=False,
                        agent_output={},
                        agent_execution_time=0.0,
                        spans=[],
                        logs=[],
                    ),
                    wait_for_completion=False,
                )

        results.compute_average_score()
        return results

        await event_bus.publish(
            EvaluationEvents.UPDATE_EVAL_SET_RUN,
            EvalSetRunUpdatedEvent(
                execution_id=self.execution_id,
                evaluator_scores=evaluator_averages,
            ),
            wait_for_completion=False,
        )

        for evaluation_result in results.evaluation_set_results:
            for run_result in evaluation_result.evaluation_run_results:
                evaluator_id = None
                for evaluator in evaluators:
                    if evaluator.name == run_result.evaluator_name:
                        evaluator_id = evaluator.id
                        break

                if evaluator_id:
                    evaluator_totals[evaluator_id] += run_result.result.score
                    evaluator_counts[evaluator_id] += 1

        # Calculate averages
        evaluator_averages = {}
        for evaluator_id in evaluator_totals:
            count = evaluator_counts[evaluator_id]
            if count > 0:
                evaluator_averages[evaluator_id] = (
                    evaluator_totals[evaluator_id] / count
                )
            else:
                evaluator_averages[evaluator_id] = 0.0

        return evaluator_averages

    async def execute_runtime(
        self, eval_item: EvaluationItem
    ) -> UiPathEvalRunExecutionOutput:
        eval_item_id = eval_item.id
        runtime_context: C = self.factory.new_context(
            execution_id=eval_item_id,
            input_json=eval_item.inputs,
            is_eval_run=True,
            log_handler=self._setup_execution_logging(eval_item_id),
        )
        attributes = {
            "evalId": eval_item.id,
            "span_type": "eval",
        }
        if runtime_context.execution_id:
            attributes["execution.id"] = runtime_context.execution_id

        start_time = time()

        try:
            result = await self.factory.execute_in_root_span(
                runtime_context, root_span=eval_item.name, attributes=attributes
            )
        except Exception as e:
            error_msg = extract_clean_error_message(e, "Agent execution error")
            raise Exception(f"Agent execution failed: {error_msg}") from None

        end_time = time()

        if runtime_context.execution_id is None:
            raise ValueError("execution_id must be set for eval runs")

        spans = self.span_exporter.get_spans(runtime_context.execution_id)
        self.span_exporter.clear(runtime_context.execution_id)

        logs = self.logs_exporter.get_logs(runtime_context.execution_id)
        self.logs_exporter.clear(runtime_context.execution_id)

        if result is None:
            raise ValueError("Execution result cannot be None for eval runs")

        return UiPathEvalRunExecutionOutput(
            execution_time=end_time - start_time,
            spans=spans,
            logs=logs,
            result=result,
        )

    def _setup_execution_logging(self, eval_item_id: str) -> ExecutionLogHandler:
        execution_log_handler = ExecutionLogHandler(eval_item_id)
        self.logs_exporter.register(eval_item_id, execution_log_handler)
        return execution_log_handler

    async def run_evaluator(
        self,
        evaluator: BaseEvaluator[Any],
        execution_output: UiPathEvalRunExecutionOutput,
        eval_item: EvaluationItem,
    ) -> EvaluationResult:
        agent_execution = AgentExecution(
            agent_input=eval_item.inputs,
            agent_output=execution_output.result.output or {},
            agent_trace=execution_output.spans,
            expected_agent_behavior=eval_item.expected_agent_behavior,
        )

        result = await evaluator.evaluate(
            agent_execution=agent_execution,
            # at the moment evaluation_criteria is always the expected output
            evaluation_criteria=eval_item.expected_output,
        )

        return result

    def _load_evaluators(
        self, evaluation_set: EvaluationSet
    ) -> List[BaseEvaluator[Any]]:
        """Load evaluators referenced by the evaluation set."""
        evaluators = []
        evaluators_dir = Path(self.context.eval_set).parent.parent / "evaluators"  # type: ignore
        evaluator_refs = set(evaluation_set.evaluator_refs)
        found_evaluator_ids = set()

        for file in evaluators_dir.glob("*.json"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"Invalid JSON in evaluator file '{file}': {str(e)}. "
                    f"Please check the file for syntax errors."
                ) from e

            try:
                evaluator_id = data.get("id")
                if evaluator_id in evaluator_refs:
                    evaluator = EvaluatorFactory.create_evaluator(data)
                    evaluators.append(evaluator)
                    found_evaluator_ids.add(evaluator_id)
            except Exception as e:
                raise ValueError(
                    f"Failed to create evaluator from file '{file}': {str(e)}. "
                    f"Please verify the evaluator configuration."
                ) from e

        missing_evaluators = evaluator_refs - found_evaluator_ids
        if missing_evaluators:
            raise ValueError(
                f"Could not find the following evaluators: {missing_evaluators}"
            )

        return evaluators

    async def cleanup(self) -> None:
        """Cleanup runtime resources."""
        pass

    async def validate(self) -> None:
        """Cleanup runtime resources."""
        pass


@dataclass
class EvalBatch:
    """Represents a batch of evaluation items to be processed together."""

    batch_id: int
    eval_items: List[EvaluationItem]


class ProgressTracker:
    """Tracks progress of evaluation execution with thread-safe updates."""

    def __init__(
        self,
        execution_id: str,
        total_evals: int,
        total_batches: int,
        event_bus: EventBus,
    ):
        self.execution_id = execution_id
        self.total_evals = total_evals
        self.total_batches = total_batches
        self.event_bus = event_bus
        self.completed_evals = 0
        self.completed_batches = 0
        self.lock = asyncio.Lock()

    async def update_eval_progress(self, count: int = 1):
        """Update progress for completed evaluations."""
        async with self.lock:
            self.completed_evals += count
            progress = (self.completed_evals / self.total_evals) * 100
            await self.event_bus.publish(
                EvaluationEvents.EVAL_PROGRESS,
                EvalProgressEvent(
                    execution_id=self.execution_id,
                    completed_evals=self.completed_evals,
                    total_evals=self.total_evals,
                    progress_percent=progress,
                ),
                wait_for_completion=False,
            )

    async def update_batch_progress(self, batch_id: int):
        """Update progress for completed batch."""
        async with self.lock:
            self.completed_batches += 1
            await self.event_bus.publish(
                EvaluationEvents.BATCH_PROGRESS,
                BatchProgressEvent(
                    execution_id=self.execution_id,
                    completed_batches=self.completed_batches,
                    total_batches=self.total_batches,
                    batch_id=batch_id,
                ),
                wait_for_completion=False,
            )


class ParallelEvalExecutor(Generic[T, C]):
    """Executor for running evaluations in parallel batches."""

    def __init__(
        self,
        max_workers: int,
        batch_size: int,
        factory: UiPathRuntimeFactory[T, C],
        event_bus: EventBus,
        context: UiPathEvalContext,
        evaluators: List[BaseEvaluator[Any]],
        span_exporter: ExecutionSpanExporter,
    ):
        self.max_workers = max_workers
        self.batch_size = batch_size
        self.factory = factory
        self.event_bus = event_bus
        self.context = context
        self.evaluators = evaluators
        self.span_exporter = span_exporter
        self.semaphore = asyncio.Semaphore(max_workers)
        self.progress_tracker = None

    def _create_batches(self, eval_items: List[EvaluationItem]) -> List[EvalBatch]:
        """Create batches from evaluation items."""
        batches = []
        for i in range(0, len(eval_items), self.batch_size):
            batch_items = eval_items[i : i + self.batch_size]
            batches.append(
                EvalBatch(batch_id=i // self.batch_size, eval_items=batch_items)
            )
        return batches

    async def execute_parallel(self, evaluation_set: EvaluationSet) -> UiPathEvalOutput:
        """Execute evaluations in parallel batches."""
        batches = self._create_batches(evaluation_set.evaluations)

        self.progress_tracker = ProgressTracker(
            execution_id=self.context.execution_id or "",
            total_evals=len(evaluation_set.evaluations),
            total_batches=len(batches),
            event_bus=self.event_bus,
        )

        tasks = []
        for batch in batches:
            task = asyncio.create_task(self._execute_batch_with_semaphore(batch))
            tasks.append(task)

        try:
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            raise ValueError(f"Error executing parallel evaluations: {str(e)}") from e

        all_results = []
        failed_batches = []

        for i, result in enumerate(batch_results):
            if isinstance(result, Exception):
                print(f"Batch {i} failed with error: {result}")
                failed_batches.append(i)

                await self.event_bus.publish(
                    EvaluationEvents.EVAL_PROGRESS,
                    EvalProgressEvent(
                        execution_id=self.context.execution_id or "",
                        completed_evals=self.progress_tracker.completed_evals
                        if self.progress_tracker
                        else 0,
                        total_evals=len(evaluation_set.evaluations),
                        progress_percent=(
                            self.progress_tracker.completed_evals
                            / len(evaluation_set.evaluations)
                        )
                        * 100
                        if self.progress_tracker
                        else 0,
                    ),
                    wait_for_completion=False,
                )
                continue
            if result:
                all_results.extend(result)

        if failed_batches:
            print(
                f"Warning: {len(failed_batches)} out of {len(batches)} batches failed. "
                f"Successfully processed {len(all_results)} evaluations."
            )

        return self._merge_results(all_results, evaluation_set.name)

    async def _execute_batch_with_semaphore(
        self, batch: EvalBatch
    ) -> List[EvaluationRunResult]:
        """Execute a batch with semaphore control."""
        async with self.semaphore:
            try:
                return await self._execute_batch(batch)
            finally:
                if self.progress_tracker:
                    await self.progress_tracker.update_batch_progress(batch.batch_id)

    async def _execute_batch(self, batch: EvalBatch) -> List[EvaluationRunResult]:
        """Execute all evaluations in a batch."""
        batch_results = []

        for eval_item in batch.eval_items:
            try:
                await self.event_bus.publish(
                    EvaluationEvents.CREATE_EVAL_RUN,
                    EvalRunCreatedEvent(
                        execution_id=self.context.execution_id or "",
                        eval_item=eval_item,
                    ),
                )

                evaluation_run_result = EvaluationRunResult(
                    evaluation_name=eval_item.name, evaluation_run_results=[]
                )

                agent_execution_output = await self._execute_runtime(eval_item)
                evaluation_item_results: List[EvalItemResult] = []

                for evaluator in self.evaluators:
                    evaluation_result = await self._run_evaluator(
                        evaluator=evaluator,
                        execution_output=agent_execution_output,
                        eval_item=eval_item,
                    )

                    dto_result = EvaluationResultDto.from_evaluation_result(
                        evaluation_result
                    )

                    evaluation_run_result.evaluation_run_results.append(
                        EvaluationRunResultDto(
                            evaluator_name=evaluator.name,
                            result=dto_result,
                        )
                    )
                    evaluation_item_results.append(
                        EvalItemResult(
                            evaluator_id=evaluator.id,
                            result=evaluation_result,
                        )
                    )

                evaluation_run_result.compute_average_score()
                batch_results.append(evaluation_run_result)

                await self.event_bus.publish(
                    EvaluationEvents.UPDATE_EVAL_RUN,
                    EvalRunUpdatedEvent(
                        execution_id=self.context.execution_id or "",
                        eval_item=eval_item,
                        eval_results=evaluation_item_results,
                        success=not agent_execution_output.result.error,
                        agent_output=agent_execution_output.result.output,
                        agent_execution_time=agent_execution_output.execution_time,
                        spans=agent_execution_output.spans,
                    ),
                    wait_for_completion=False,
                )

                if self.progress_tracker:
                    await self.progress_tracker.update_eval_progress()

            except Exception as e:
                print(f"Error executing evaluation {eval_item.name}: {str(e)}")

                failed_result = EvaluationRunResult(
                    evaluation_name=eval_item.name, evaluation_run_results=[]
                )
                failed_result.score = 0.0
                batch_results.append(failed_result)

                if self.progress_tracker:
                    await self.progress_tracker.update_eval_progress()
                continue

        return batch_results

    async def _execute_runtime(
        self, eval_item: EvaluationItem
    ) -> UiPathEvalRunExecutionOutput:
        """Execute runtime for a single evaluation item."""
        runtime_context: C = self.factory.new_context(
            execution_id=eval_item.id,
            input_json=eval_item.inputs,
            is_eval_run=True,
        )
        attributes = {
            "evalId": eval_item.id,
            "span_type": "eval",
        }
        if runtime_context.execution_id:
            attributes["execution.id"] = runtime_context.execution_id

        start_time = time()

        result = await self.factory.execute_in_root_span(
            runtime_context, root_span=eval_item.name, attributes=attributes
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

    async def _run_evaluator(
        self,
        evaluator: BaseEvaluator[Any],
        execution_output: UiPathEvalRunExecutionOutput,
        eval_item: EvaluationItem,
    ) -> EvaluationResult:
        """Run a single evaluator."""
        agent_execution = AgentExecution(
            agent_input=eval_item.inputs,
            agent_output=execution_output.result.output or {},
            agent_trace=execution_output.spans,
            expected_agent_behavior=eval_item.expected_agent_behavior,
        )

        result = await evaluator.evaluate(
            agent_execution=agent_execution,
            evaluation_criteria=eval_item.expected_output,
        )

        return result

    def _merge_results(
        self, batch_results: List[EvaluationRunResult], eval_set_name: str
    ) -> UiPathEvalOutput:
        """Merge results from all batches into final output."""
        results = UiPathEvalOutput(
            evaluation_set_name=eval_set_name,
            score=0,
            evaluation_set_results=batch_results,
        )
        results.compute_average_score()
        return results
