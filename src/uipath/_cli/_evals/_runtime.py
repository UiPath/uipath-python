import asyncio
import json
import logging
import os
import uuid
from collections import defaultdict
from pathlib import Path
from time import time
from typing import Any, Dict, Generic, List, Optional, Sequence, TypeVar

from opentelemetry import context as context_api
from opentelemetry.sdk.trace import ReadableSpan, Span
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

from uipath._cli._evals.mocks.cache_manager import CacheManager
from uipath._cli._evals.mocks.input_mocker import (
    generate_llm_input,
)

from ..._events._event_bus import EventBus
from ..._events._events import (
    EvalItemExceptionDetails,
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
    UiPathErrorCategory,
    UiPathErrorContract,
    UiPathExecutionBatchTraceProcessor,
    UiPathRuntimeContext,
    UiPathRuntimeFactory,
    UiPathRuntimeResult,
    UiPathRuntimeStatus,
)
from .._runtime._logging import ExecutionLogHandler
from .._utils._eval_set import EvalHelpers
from ..models.runtime_schema import Entrypoint
from ._evaluator_factory import EvaluatorFactory
from ._models._evaluation_set import (
    EvaluationItem,
    EvaluationSet,
)
from ._models._exceptions import EvaluationRuntimeException
from ._models._output import (
    EvaluationResultDto,
    EvaluationRunResult,
    EvaluationRunResultDto,
    UiPathEvalOutput,
    UiPathEvalRunExecutionOutput,
    convert_eval_execution_output_to_serializable,
)
from ._span_collection import ExecutionSpanCollector
from .mocks.mocks import (
    cache_manager_context,
    clear_execution_context,
    set_execution_context,
)

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


class ExecutionSpanProcessor(UiPathExecutionBatchTraceProcessor):
    """Span processor that adds spans to ExecutionSpanCollector when they start."""

    def __init__(self, span_exporter: SpanExporter, collector: ExecutionSpanCollector):
        super().__init__(span_exporter)
        self.collector = collector

    def on_start(
        self, span: Span, parent_context: Optional[context_api.Context] = None
    ) -> None:
        super().on_start(span, parent_context)

        if span.attributes and "execution.id" in span.attributes:
            exec_id = span.attributes["execution.id"]
            if isinstance(exec_id, str):
                self.collector.add_span(span, exec_id)


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
    eval_set_run_id: Optional[str] = None
    verbose: bool = False
    enable_mocker_cache: bool = False


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
        self.span_collector: ExecutionSpanCollector = ExecutionSpanCollector()

        # Span processor feeds both exporter and collector
        span_processor = ExecutionSpanProcessor(self.span_exporter, self.span_collector)
        self.factory.tracer_span_processors.append(span_processor)
        self.factory.tracer_provider.add_span_processor(span_processor)

        self.logs_exporter: ExecutionLogsExporter = ExecutionLogsExporter()
        self.execution_id = str(uuid.uuid4())
        self.entrypoint: Optional[Entrypoint] = None

    async def get_entrypoint(self):
        if not self.entrypoint:
            temp_runtime = self.factory.new_runtime(
                entrypoint=self.context.entrypoint, runtime_dir=os.getcwd()
            )
            self.entrypoint = await temp_runtime.get_entrypoint()
        return self.entrypoint

    @classmethod
    def from_eval_context(
        cls,
        context: UiPathEvalContext,
        factory: UiPathRuntimeFactory[T, C],
        event_bus: EventBus,
    ) -> "UiPathEvalRuntime[T, C]":
        return cls(context, factory, event_bus)

    async def execute(self) -> UiPathRuntimeResult:
        if self.context.eval_set is None:
            raise ValueError("eval_set must be provided for evaluation runs")

        event_bus = self.event_bus

        # Create cache manager if enabled
        if self.context.enable_mocker_cache:
            cache_mgr = CacheManager()
            cache_manager_context.set(cache_mgr)

        try:
            # Load eval set (path is already resolved in cli_eval.py)
            evaluation_set, _ = EvalHelpers.load_eval_set(
                self.context.eval_set, self.context.eval_ids
            )
            evaluators = self._load_evaluators(evaluation_set)

            await event_bus.publish(
                EvaluationEvents.CREATE_EVAL_SET_RUN,
                EvalSetRunCreatedEvent(
                    execution_id=self.execution_id,
                    entrypoint=self.context.entrypoint or "",
                    eval_set_run_id=self.context.eval_set_run_id,
                    eval_set_id=evaluation_set.id,
                    no_of_evals=len(evaluation_set.evaluations),
                    evaluators=evaluators,
                ),
            )

            # Check if parallel execution should be used
            if (
                self.context.workers
                and self.context.workers > 1
                and len(evaluation_set.evaluations) > 1
            ):
                eval_run_result_list = await self._execute_parallel(
                    evaluation_set, evaluators, event_bus, self.context.workers
                )
            else:
                eval_run_result_list = await self._execute_sequential(
                    evaluation_set, evaluators, event_bus
                )
            results = UiPathEvalOutput(
                evaluation_set_name=evaluation_set.name,
                evaluation_set_results=eval_run_result_list,
            )
        finally:
            # Flush cache to disk at end of eval set and cleanup
            if self.context.enable_mocker_cache:
                cache_manager = cache_manager_context.get()
                if cache_manager is not None:
                    cache_manager.flush()
                cache_manager_context.set(None)

        # Computing evaluator averages
        evaluator_averages: Dict[str, float] = defaultdict(float)
        evaluator_count: Dict[str, int] = defaultdict(int)

        for eval_run_result in results.evaluation_set_results:
            for result_dto in eval_run_result.evaluation_run_results:
                evaluator_averages[result_dto.evaluator_id] += result_dto.result.score
                evaluator_count[result_dto.evaluator_id] += 1

        for eval_id in evaluator_averages:
            evaluator_averages[eval_id] = (
                evaluator_averages[eval_id] / evaluator_count[eval_id]
            )
        await event_bus.publish(
            EvaluationEvents.UPDATE_EVAL_SET_RUN,
            EvalSetRunUpdatedEvent(
                execution_id=self.execution_id,
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
        self,
        evaluation_set: EvaluationSet,
        evaluators: List[BaseEvaluator[Any, Any, Any]],
        event_bus: EventBus,
    ) -> List[EvaluationRunResult]:
        all_eval_run_result: list[EvaluationRunResult] = []

        for eval_item in evaluation_set.evaluations:
            all_eval_run_result.append(
                await self._execute_eval(eval_item, evaluators, event_bus)
            )

        return all_eval_run_result

    async def _execute_parallel(
        self,
        evaluation_set: EvaluationSet,
        evaluators: List[BaseEvaluator[Any, Any, Any]],
        event_bus: EventBus,
        workers: int,
    ) -> List[EvaluationRunResult]:
        # Create a queue with max concurrency
        queue: asyncio.Queue[tuple[int, EvaluationItem]] = asyncio.Queue(
            maxsize=workers
        )

        # Dictionary to store results with their original indices
        results_dict: Dict[int, EvaluationRunResult] = {}

        # Producer task to fill the queue
        async def producer() -> None:
            for index, eval_item in enumerate(evaluation_set.evaluations):
                await queue.put((index, eval_item))
            # Signal completion by putting None markers
            for _ in range(workers):
                await queue.put(None)  # type: ignore

        # Worker function to process items from the queue
        async def worker(worker_id: int) -> None:
            while True:
                item = await queue.get()

                # Check for termination signal
                if item is None:
                    queue.task_done()
                    break

                index, eval_item = item

                try:
                    # Execute the evaluation
                    result = await self._execute_eval(eval_item, evaluators, event_bus)

                    # Store result with its index to maintain order
                    results_dict[index] = result
                finally:
                    # Mark the task as done
                    queue.task_done()

        # Start producer
        producer_task = asyncio.create_task(producer())

        # Create worker tasks based on workers
        worker_tasks = [asyncio.create_task(worker(i)) for i in range(workers)]

        # Wait for producer and all workers to complete
        await producer_task
        await asyncio.gather(*worker_tasks)

        # Return results in the original order
        return [results_dict[i] for i in range(len(evaluation_set.evaluations))]

    async def _execute_eval(
        self,
        eval_item: EvaluationItem,
        evaluators: List[BaseEvaluator[Any, Any, Any]],
        event_bus: EventBus,
    ) -> EvaluationRunResult:
        # Generate LLM-based input if input_mocking_strategy is defined
        if eval_item.input_mocking_strategy:
            eval_item = await self._generate_input_for_eval(eval_item)

        execution_id = str(uuid.uuid4())

        set_execution_context(eval_item, self.span_collector, execution_id)

        await event_bus.publish(
            EvaluationEvents.CREATE_EVAL_RUN,
            EvalRunCreatedEvent(
                execution_id=execution_id,
                eval_item=eval_item,
            ),
        )

        evaluation_run_results = EvaluationRunResult(
            evaluation_name=eval_item.name, evaluation_run_results=[]
        )

        try:
            try:
                agent_execution_output = await self.execute_runtime(
                    eval_item, execution_id
                )
            except Exception as e:
                if self.context.verbose:
                    if isinstance(e, EvaluationRuntimeException):
                        spans = e.spans
                        logs = e.logs
                        execution_time = e.execution_time
                        loggable_error = e.root_exception
                    else:
                        spans = []
                        logs = []
                        execution_time = 0
                        loggable_error = e

                    error_info = UiPathErrorContract(
                        code="RUNTIME_SHUTDOWN_ERROR",
                        title="Runtime shutdown failed",
                        detail=f"Error: {str(loggable_error)}",
                        category=UiPathErrorCategory.UNKNOWN,
                    )
                    error_result = UiPathRuntimeResult(
                        status=UiPathRuntimeStatus.FAULTED,
                        error=error_info,
                    )
                    evaluation_run_results.agent_execution_output = (
                        convert_eval_execution_output_to_serializable(
                            UiPathEvalRunExecutionOutput(
                                execution_time=execution_time,
                                result=error_result,
                                spans=spans,
                                logs=logs,
                            )
                        )
                    )
                raise

            if self.context.verbose:
                evaluation_run_results.agent_execution_output = (
                    convert_eval_execution_output_to_serializable(
                        agent_execution_output
                    )
                )
            evaluation_item_results: list[EvalItemResult] = []

            for evaluator in evaluators:
                if evaluator.id not in eval_item.evaluation_criterias:
                    # Skip!
                    continue
                evaluation_criteria = eval_item.evaluation_criterias[evaluator.id]

                evaluation_result = await self.run_evaluator(
                    evaluator=evaluator,
                    execution_output=agent_execution_output,
                    eval_item=eval_item,
                    evaluation_criteria=evaluator.evaluation_criteria_type(
                        **evaluation_criteria
                    )
                    if evaluation_criteria
                    else evaluator.evaluator_config.default_evaluation_criteria,
                )

                dto_result = EvaluationResultDto.from_evaluation_result(
                    evaluation_result
                )

                evaluation_run_results.evaluation_run_results.append(
                    EvaluationRunResultDto(
                        evaluator_name=evaluator.name,
                        result=dto_result,
                        evaluator_id=evaluator.id,
                    )
                )
                evaluation_item_results.append(
                    EvalItemResult(
                        evaluator_id=evaluator.id,
                        result=evaluation_result,
                    )
                )

            await event_bus.publish(
                EvaluationEvents.UPDATE_EVAL_RUN,
                EvalRunUpdatedEvent(
                    execution_id=execution_id,
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
            exception_details = EvalItemExceptionDetails(exception=e)

            for evaluator in evaluators:
                evaluation_run_results.evaluation_run_results.append(
                    EvaluationRunResultDto(
                        evaluator_name=evaluator.name,
                        evaluator_id=evaluator.id,
                        result=EvaluationResultDto(score=0),
                    )
                )

            eval_run_updated_event = EvalRunUpdatedEvent(
                execution_id=execution_id,
                eval_item=eval_item,
                eval_results=[],
                success=False,
                agent_output={},
                agent_execution_time=0.0,
                exception_details=exception_details,
                spans=[],
                logs=[],
            )
            if isinstance(e, EvaluationRuntimeException):
                eval_run_updated_event.spans = e.spans
                eval_run_updated_event.logs = e.logs
                eval_run_updated_event.exception_details.exception = (  # type: ignore
                    e.root_exception
                )
                eval_run_updated_event.exception_details.runtime_exception = True  # type: ignore

            await event_bus.publish(
                EvaluationEvents.UPDATE_EVAL_RUN,
                eval_run_updated_event,
                wait_for_completion=False,
            )
        finally:
            clear_execution_context()

        return evaluation_run_results

    async def _generate_input_for_eval(
        self, eval_item: EvaluationItem
    ) -> EvaluationItem:
        """Use LLM to generate a mock input for an evaluation item."""
        generated_input = await generate_llm_input(
            eval_item, (await self.get_entrypoint()).input
        )
        updated_eval_item = eval_item.model_copy(update={"inputs": generated_input})
        return updated_eval_item

    def _get_and_clear_execution_data(
        self, execution_id: str
    ) -> tuple[List[ReadableSpan], list[logging.LogRecord]]:
        spans = self.span_exporter.get_spans(execution_id)
        self.span_exporter.clear(execution_id)
        self.span_collector.clear(execution_id)

        logs = self.logs_exporter.get_logs(execution_id)
        self.logs_exporter.clear(execution_id)

        return spans, logs

    async def execute_runtime(
        self, eval_item: EvaluationItem, execution_id: str
    ) -> UiPathEvalRunExecutionOutput:
        context_args = self.context.model_dump()
        context_args["execution_id"] = execution_id
        context_args["input_json"] = eval_item.inputs
        context_args["is_eval_run"] = True
        context_args["log_handler"] = self._setup_execution_logging(execution_id)
        runtime_context: C = self.factory.new_context(**context_args)
        if runtime_context.execution_id is None:
            raise ValueError("execution_id must be set for eval runs")

        attributes = {
            "evalId": eval_item.id,
            "span_type": "eval",
            "execution.id": runtime_context.execution_id,
        }

        start_time = time()
        try:
            result = await self.factory.execute_in_root_span(
                runtime_context, root_span=eval_item.name, attributes=attributes
            )
        except Exception as e:
            end_time = time()
            spans, logs = self._get_and_clear_execution_data(
                runtime_context.execution_id
            )
            raise EvaluationRuntimeException(
                spans=spans,
                logs=logs,
                root_exception=e,
                execution_time=end_time - start_time,
            ) from e

        end_time = time()
        spans, logs = self._get_and_clear_execution_data(runtime_context.execution_id)

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
        evaluator: BaseEvaluator[Any, Any, Any],
        execution_output: UiPathEvalRunExecutionOutput,
        eval_item: EvaluationItem,
        *,
        evaluation_criteria: Any,
    ) -> EvaluationResult:
        agent_execution = AgentExecution(
            agent_input=eval_item.inputs,
            agent_output=execution_output.result.output or {},
            agent_trace=execution_output.spans,
            expected_agent_behavior=eval_item.expected_agent_behavior,
        )

        result = await evaluator.validate_and_evaluate_criteria(
            agent_execution=agent_execution,
            evaluation_criteria=evaluation_criteria,
        )

        return result

    def _load_evaluators(
        self, evaluation_set: EvaluationSet
    ) -> list[BaseEvaluator[Any, Any, Any]]:
        """Load evaluators referenced by the evaluation set."""
        evaluators = []
        evaluators_dir = Path(self.context.eval_set).parent.parent / "evaluators"  # type: ignore

        # If evaluatorConfigs is specified, use that (new field with weights)
        # Otherwise, fall back to evaluatorRefs (old field without weights)
        if (
            hasattr(evaluation_set, "evaluator_configs")
            and evaluation_set.evaluator_configs
        ):
            # Use new evaluatorConfigs field - supports weights
            evaluator_ref_ids = {ref.ref for ref in evaluation_set.evaluator_configs}
        else:
            # Fall back to old evaluatorRefs field - plain strings
            evaluator_ref_ids = set(evaluation_set.evaluator_refs)

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
                if evaluator_id in evaluator_ref_ids:
                    evaluator = EvaluatorFactory.create_evaluator(data, evaluators_dir)
                    evaluators.append(evaluator)
                    found_evaluator_ids.add(evaluator_id)
            except Exception as e:
                raise ValueError(
                    f"Failed to create evaluator from file '{file}': {str(e)}. "
                    f"Please verify the evaluator configuration."
                ) from e

        missing_evaluators = evaluator_ref_ids - found_evaluator_ids
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
