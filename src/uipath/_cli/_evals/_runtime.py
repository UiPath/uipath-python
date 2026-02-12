import json
import logging
from collections import defaultdict
from contextlib import contextmanager
from time import time
from typing import (
    Any,
    Awaitable,
    Iterable,
    Iterator,
    Protocol,
    Sequence,
    Tuple,
    runtime_checkable,
)

import coverage
from opentelemetry import context as context_api
from opentelemetry.sdk.trace import ReadableSpan, Span
from opentelemetry.sdk.trace.export import (
    SpanExporter,
    SpanExportResult,
)
from opentelemetry.trace import (
    NonRecordingSpan,
    SpanContext,
    Status,
    StatusCode,
    TraceFlags,
    use_span,
)
from pydantic import BaseModel
from uipath.core.tracing import UiPathTraceManager
from uipath.core.tracing.processors import UiPathExecutionBatchTraceProcessor
from uipath.runtime import (
    UiPathExecuteOptions,
    UiPathExecutionRuntime,
    UiPathRuntimeFactoryProtocol,
    UiPathRuntimeResult,
    UiPathRuntimeStatus,
    UiPathRuntimeStorageProtocol,
)
from uipath.runtime.errors import (
    UiPathErrorCategory,
    UiPathErrorContract,
)
from uipath.runtime.logging import UiPathRuntimeExecutionLogHandler
from uipath.runtime.schema import UiPathRuntimeSchema

from uipath._cli._evals._conversational_mapper import (
    to_conversational_eval_output_schema
)

from uipath._cli._evals._span_utils import (
    configure_eval_set_run_span,
    configure_evaluation_span,
    set_evaluation_output_span_output,
)
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
from ...eval.evaluators.base_evaluator import GenericBaseEvaluator
from ...eval.models import EvaluationResult
from ...eval.models.models import AgentExecution, EvalItemResult
from .._utils._parallelization import execute_parallel
from ._eval_util import apply_input_overrides
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
from .mocks.types import MockingContext

logger = logging.getLogger(__name__)


@runtime_checkable
class LLMAgentRuntimeProtocol(Protocol):
    """Protocol for runtimes that can provide agent model information.

    Runtimes that implement this protocol can be queried for
    the agent's configured LLM model, enabling features like 'same-as-agent'
    model resolution for evaluators.
    """

    def get_agent_model(self) -> str | None:
        """Return the agent's configured LLM model name.

        Returns:
            The model name from agent settings (e.g., 'gpt-4o-2024-11-20'),
            or None if no model is configured.
        """
        ...


class ExecutionSpanExporter(SpanExporter):
    """Custom exporter that stores spans grouped by execution ids."""

    def __init__(self):
        # { execution_id -> list of spans }
        self._spans: dict[str, list[ReadableSpan]] = defaultdict(list)

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        for span in spans:
            if span.attributes is not None:
                exec_id = span.attributes.get("execution.id")
                if exec_id is not None and isinstance(exec_id, str):
                    self._spans[exec_id].append(span)

        return SpanExportResult.SUCCESS

    def get_spans(self, execution_id: str) -> list[ReadableSpan]:
        """Retrieve spans for a given execution id."""
        return self._spans.get(execution_id, [])

    def clear(self, execution_id: str | None = None) -> None:
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
        self, span: Span, parent_context: context_api.Context | None = None
    ) -> None:
        super().on_start(span, parent_context)

        if span.attributes and "execution.id" in span.attributes:
            exec_id = span.attributes["execution.id"]
            if isinstance(exec_id, str):
                self.collector.add_span(span, exec_id)


class ExecutionLogsExporter:
    """Custom exporter that stores multiple execution log handlers."""

    def __init__(self):
        self._log_handlers: dict[str, UiPathRuntimeExecutionLogHandler] = {}

    def register(
        self, execution_id: str, handler: UiPathRuntimeExecutionLogHandler
    ) -> None:
        self._log_handlers[execution_id] = handler

    def get_logs(self, execution_id: str) -> list[logging.LogRecord]:
        """Clear stored spans for one or all executions."""
        log_handler = self._log_handlers.get(execution_id)
        return log_handler.buffer if log_handler else []

    def clear(self, execution_id: str | None = None) -> None:
        """Clear stored spans for one or all executions."""
        if execution_id:
            self._log_handlers.pop(execution_id, None)
        else:
            self._log_handlers.clear()


class UiPathEvalContext:
    """Context used for evaluation runs."""

    # Required Fields
    runtime_schema: UiPathRuntimeSchema
    evaluation_set: EvaluationSet
    evaluators: list[GenericBaseEvaluator[Any, Any, Any]]
    execution_id: str

    # Optional Fields
    entrypoint: str | None = None
    workers: int | None = 1
    eval_set_run_id: str | None = None
    verbose: bool = False
    enable_mocker_cache: bool = False
    report_coverage: bool = False
    input_overrides: dict[str, Any] | None = None
    resume: bool = False
    job_id: str | None = None


class UiPathEvalRuntime:
    """Specialized runtime for evaluation runs, with access to the factory."""

    def __init__(
        self,
        context: UiPathEvalContext,
        factory: UiPathRuntimeFactoryProtocol,
        trace_manager: UiPathTraceManager,
        event_bus: EventBus,
    ):
        self.context: UiPathEvalContext = context
        self.factory: UiPathRuntimeFactoryProtocol = factory
        self.event_bus: EventBus = event_bus
        self.trace_manager: UiPathTraceManager = trace_manager
        self.span_exporter: ExecutionSpanExporter = ExecutionSpanExporter()
        self.span_collector: ExecutionSpanCollector = ExecutionSpanCollector()

        # Span processor feeds both exporter and collector
        span_processor = ExecutionSpanProcessor(self.span_exporter, self.span_collector)
        self.trace_manager.tracer_span_processors.append(span_processor)
        self.trace_manager.tracer_provider.add_span_processor(span_processor)

        self.logs_exporter: ExecutionLogsExporter = ExecutionLogsExporter()
        logger.debug(
            f"EVAL RUNTIME INIT: job_id={context.job_id}, "
            f"eval_set_run_id={context.eval_set_run_id}"
        )
        self.execution_id = context.execution_id
        logger.info(f"EVAL RUNTIME: execution_id set to: {self.execution_id}")
        self.coverage = coverage.Coverage(branch=True)

        self._storage: UiPathRuntimeStorageProtocol | None = None

    async def __aenter__(self) -> "UiPathEvalRuntime":
        if self.context.report_coverage:
            self.coverage.start()
        self._storage = await self.factory.get_storage()

        return self

    async def __aexit__(self, *args: Any) -> None:
        if self.context.report_coverage:
            self.coverage.stop()
            self.coverage.report(include=["./*"], show_missing=True)

    async def get_schema(self) -> UiPathRuntimeSchema:
        return self.context.runtime_schema

    @contextmanager
    def _mocker_cache(self) -> Iterator[None]:
        # Create cache manager if enabled
        if self.context.enable_mocker_cache:
            cache_mgr = CacheManager()
            cache_manager_context.set(cache_mgr)
        try:
            yield
        finally:
            # Flush cache to disk at end of eval set and cleanup
            if self.context.enable_mocker_cache:
                cache_manager = cache_manager_context.get()
                if cache_manager is not None:
                    cache_manager.flush()
                cache_manager_context.set(None)

    async def initiate_evaluation(
        self,
    ) -> Tuple[
        EvaluationSet,
        list[GenericBaseEvaluator[Any, Any, Any]],
        Iterable[Awaitable[EvaluationRunResult]],
    ]:
        # Validate that resume mode is not used with multiple evaluations
        if self.context.resume and len(self.context.evaluation_set.evaluations) > 1:
            raise ValueError(
                f"Resume mode is not supported with multiple evaluations. "
                f"Found {len(self.context.evaluation_set.evaluations)} evaluations in the set. "
                f"Please run with a single evaluation using --eval-ids to specify one evaluation."
            )

        await self.event_bus.publish(
            EvaluationEvents.CREATE_EVAL_SET_RUN,
            EvalSetRunCreatedEvent(
                execution_id=self.execution_id,
                entrypoint=self.context.entrypoint or "",
                eval_set_run_id=self.context.eval_set_run_id,
                eval_set_id=self.context.evaluation_set.id,
                no_of_evals=len(self.context.evaluation_set.evaluations),
                evaluators=self.context.evaluators,
            ),
        )

        return (
            self.context.evaluation_set,
            self.context.evaluators,
            (
                self._execute_eval(eval_item, self.context.evaluators)
                for eval_item in self.context.evaluation_set.evaluations
            ),
        )

    async def execute(self) -> UiPathRuntimeResult:
        print("EXECUTEE!!!")
        logger.info("=" * 80)
        logger.info("EVAL RUNTIME: Starting evaluation execution")
        logger.info(f"EVAL RUNTIME: Execution ID: {self.execution_id}")
        logger.info(f"EVAL RUNTIME: Job ID: {self.context.job_id}")
        logger.info(f"EVAL RUNTIME: Resume mode: {self.context.resume}")
        logger.info("=" * 80)

        with self._mocker_cache():
            tracer = self.trace_manager.tracer_provider.get_tracer(__name__)

            # During resume, restore the parent "Evaluation Set Run" span context
            # This prevents creating duplicate eval set run spans across jobs
            eval_set_parent_span = await self._restore_parent_span(
                "eval_set_run", "Evaluation Set Run"
            )

            # Create "Evaluation Set Run" span or use restored parent context
            # NOTE: Do NOT set execution.id on this parent span, as the mixin in
            # UiPathExecutionBatchTraceProcessor propagates execution.id from parent
            # to child spans, which would overwrite the per-eval execution.id
            span_attributes: dict[str, str | bool] = {
                "span_type": "eval_set_run",
                "uipath.custom_instrumentation": True,
            }
            if self.context.eval_set_run_id:
                span_attributes["eval_set_run_id"] = self.context.eval_set_run_id

            eval_set_span_context_manager = (
                use_span(
                    eval_set_parent_span, end_on_exit=False
                )  # Don't end the remote span
                if eval_set_parent_span
                else tracer.start_as_current_span(
                    "Evaluation Set Run", attributes=span_attributes
                )
            )

            with eval_set_span_context_manager as span:
                await self._save_span_context_for_resume(
                    span, "eval_set_run", "Evaluation Set Run"
                )

                try:
                    (
                        evaluation_set,
                        evaluators,
                        evaluation_iterable,
                    ) = await self.initiate_evaluation()
                    workers = self.context.workers or 1
                    assert workers >= 1
                    eval_run_result_list = await execute_parallel(
                        evaluation_iterable, workers
                    )
                    results = UiPathEvalOutput(
                        evaluation_set_name=evaluation_set.name,
                        evaluation_set_results=eval_run_result_list,
                    )

                    # Computing evaluator averages
                    evaluator_averages: dict[str, float] = defaultdict(float)
                    evaluator_count: dict[str, int] = defaultdict(int)

                    # Check if any eval runs failed
                    any_failed = False
                    for eval_run_result in results.evaluation_set_results:
                        # Check if the agent execution had an error
                        if (
                            eval_run_result.agent_execution_output
                            and eval_run_result.agent_execution_output.result.error
                        ):
                            any_failed = True

                        for result_dto in eval_run_result.evaluation_run_results:
                            evaluator_averages[result_dto.evaluator_name] += (
                                result_dto.result.score
                            )
                            evaluator_count[result_dto.evaluator_name] += 1

                    for eval_id in evaluator_averages:
                        evaluator_averages[eval_id] = (
                            evaluator_averages[eval_id] / evaluator_count[eval_id]
                        )

                    # Configure span with output and metadata
                    await configure_eval_set_run_span(
                        span=span,
                        evaluator_averages=evaluator_averages,
                        execution_id=self.execution_id,
                        schema=await self.get_schema(),
                        success=not any_failed,
                    )

                    await self.event_bus.publish(
                        EvaluationEvents.UPDATE_EVAL_SET_RUN,
                        EvalSetRunUpdatedEvent(
                            execution_id=self.execution_id,
                            evaluator_scores=evaluator_averages,
                            success=not any_failed,
                        ),
                        wait_for_completion=False,
                    )

                    # Collect triggers from all evaluation runs (pass-through from inner runtime)
                    logger.info("=" * 80)
                    logger.info(
                        "EVAL RUNTIME: Collecting triggers from all evaluation runs"
                    )
                    all_triggers = []
                    for eval_run_result in results.evaluation_set_results:
                        if (
                            eval_run_result.agent_execution_output
                            and eval_run_result.agent_execution_output.result
                        ):
                            runtime_result = (
                                eval_run_result.agent_execution_output.result
                            )
                            if runtime_result.triggers:
                                all_triggers.extend(runtime_result.triggers)

                    if all_triggers:
                        logger.info(
                            f"EVAL RUNTIME: ✅ Passing through {len(all_triggers)} trigger(s) to top-level result"
                        )
                        for i, trigger in enumerate(all_triggers, 1):
                            logger.info(
                                f"EVAL RUNTIME: Pass-through trigger {i}: {trigger.model_dump(by_alias=True)}"
                            )
                    else:
                        logger.info("EVAL RUNTIME: No triggers to pass through")
                    logger.info("=" * 80)

                    # Determine overall status - propagate status from inner runtime
                    # This is critical for serverless executor to know to save state and suspend job
                    # Priority: SUSPENDED > FAULTED > SUCCESSFUL
                    overall_status = UiPathRuntimeStatus.SUCCESSFUL
                    for eval_run_result in results.evaluation_set_results:
                        if (
                            eval_run_result.agent_execution_output
                            and eval_run_result.agent_execution_output.result
                        ):
                            inner_status = (
                                eval_run_result.agent_execution_output.result.status
                            )
                            if inner_status == UiPathRuntimeStatus.SUSPENDED:
                                overall_status = UiPathRuntimeStatus.SUSPENDED
                                logger.info(
                                    "EVAL RUNTIME: Propagating SUSPENDED status from inner runtime"
                                )
                                break  # SUSPENDED takes highest priority, stop checking
                            elif inner_status == UiPathRuntimeStatus.FAULTED:
                                overall_status = UiPathRuntimeStatus.FAULTED
                                # Continue checking in case a later eval is SUSPENDED

                    result = UiPathRuntimeResult(
                        output={**results.model_dump(by_alias=True)},
                        status=overall_status,
                        triggers=all_triggers if all_triggers else None,
                    )
                    return result
                except Exception as e:
                    # Set span status to ERROR on exception
                    span.set_status(Status(StatusCode.ERROR, str(e)))

                    # Publish failure event for eval set run
                    await self.event_bus.publish(
                        EvaluationEvents.UPDATE_EVAL_SET_RUN,
                        EvalSetRunUpdatedEvent(
                            execution_id=self.execution_id,
                            evaluator_scores={},
                            success=False,
                        ),
                        wait_for_completion=False,
                    )
                    raise

    async def _execute_eval(
        self,
        eval_item: EvaluationItem,
        evaluators: list[GenericBaseEvaluator[Any, Any, Any]],
    ) -> EvaluationRunResult:
        execution_id = str(eval_item.id)

        tracer = self.trace_manager.tracer_provider.get_tracer(__name__)

        # During resume, restore the parent span context from the previous execution
        # This allows evaluators to be properly parented to the original "Evaluation" span
        parent_span = await self._restore_parent_span(eval_item.id, "Evaluation")

        # Create "Evaluation" span or use restored parent context
        # use_span() handles context management automatically (no manual attach/detach)
        span_context_manager = (
            use_span(parent_span, end_on_exit=False)  # Don't end the remote span
            if parent_span
            else tracer.start_as_current_span(
                "Evaluation",
                attributes={
                    "execution.id": execution_id,
                    "span_type": "evaluation",
                    "eval_item_id": eval_item.id,
                    "eval_item_name": eval_item.name,
                    "uipath.custom_instrumentation": True,
                },
            )
        )

        with span_context_manager as span:
            await self._save_span_context_for_resume(span, eval_item.id, "Evaluation")

            evaluation_run_results = EvaluationRunResult(
                evaluation_name=eval_item.name, evaluation_run_results=[]
            )

            try:
                try:
                    # Generate LLM-based input if input_mocking_strategy is defined
                    if eval_item.input_mocking_strategy:
                        eval_item = await self._generate_input_for_eval(eval_item)

                    set_execution_context(
                        MockingContext(
                            strategy=eval_item.mocking_strategy,
                            name=eval_item.name,
                            inputs=eval_item.inputs,
                        ),
                        span_collector=self.span_collector,
                        execution_id=execution_id,
                    )

                    # Only create eval run entry if NOT resuming from a checkpoint
                    # When resuming, the entry already exists from the suspend phase
                    # The progress reporter will load the eval_run_id from persisted state
                    if not self.context.resume:
                        await self.event_bus.publish(
                            EvaluationEvents.CREATE_EVAL_RUN,
                            EvalRunCreatedEvent(
                                execution_id=execution_id,
                                eval_item=eval_item,
                            ),
                        )
                    agent_execution_output = await self.execute_runtime(
                        eval_item,
                        execution_id,
                        input_overrides=self.context.input_overrides,
                    )

                    logger.info(
                        f"DEBUG: Agent execution result status: {agent_execution_output.result.status}"
                    )
                    logger.info(
                        f"DEBUG: Agent execution result trigger: {agent_execution_output.result.trigger}"
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

                # Check if execution was suspended (e.g., waiting for RPA job completion)
                if (
                    agent_execution_output.result.status
                    == UiPathRuntimeStatus.SUSPENDED
                ):
                    # For suspended executions, we don't run evaluators yet
                    # The serverless executor should save the triggers and resume later
                    logger.info("=" * 80)
                    logger.info(
                        f"🔴 EVAL RUNTIME: DETECTED SUSPENSION for eval '{eval_item.name}' (id: {eval_item.id})"
                    )
                    logger.info("EVAL RUNTIME: Agent returned SUSPENDED status")

                    # Extract triggers from result
                    triggers = []
                    if agent_execution_output.result.trigger:
                        triggers.append(agent_execution_output.result.trigger)
                    if agent_execution_output.result.triggers:
                        triggers.extend(agent_execution_output.result.triggers)

                    logger.info(
                        f"EVAL RUNTIME: Extracted {len(triggers)} trigger(s) from suspended execution"
                    )
                    for i, trigger in enumerate(triggers, 1):
                        logger.info(
                            f"EVAL RUNTIME: Trigger {i}: {trigger.model_dump(by_alias=True)}"
                        )

                    logger.info("=" * 80)

                    # IMPORTANT: Always include execution output with triggers when suspended
                    # This ensures triggers are visible in the output JSON for serverless executor
                    evaluation_run_results.agent_execution_output = (
                        convert_eval_execution_output_to_serializable(
                            agent_execution_output
                        )
                    )

                    # DO NOT update evalRun status when suspended!
                    # The evalRun should remain in IN_PROGRESS state until the agent completes
                    # and evaluators run. When the execution resumes, the evaluators will run
                    # and the evalRun will be properly updated with results.
                    logger.info(
                        "EVAL RUNTIME: Skipping evalRun update - keeping status as IN_PROGRESS until resume"
                    )

                    # Return partial results with trigger information
                    # The evaluation will be completed when resumed
                    return evaluation_run_results

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
                        # If evaluation criteria is None, validate_and_evaluate defaults to the default
                        evaluation_criteria=evaluator.evaluation_criteria_type(
                            **evaluation_criteria
                        )
                        if evaluation_criteria
                        else None,
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

                exception_details = None
                agent_output = agent_execution_output.result.output
                if agent_execution_output.result.status == UiPathRuntimeStatus.FAULTED:
                    error = agent_execution_output.result.error
                    if error is not None:
                        # we set the exception details for the run event
                        # Convert error contract to exception
                        error_exception = Exception(
                            f"{error.title}: {error.detail} (code: {error.code})"
                        )
                        exception_details = EvalItemExceptionDetails(
                            exception=error_exception
                        )
                        agent_output = error.model_dump()

                await self.event_bus.publish(
                    EvaluationEvents.UPDATE_EVAL_RUN,
                    EvalRunUpdatedEvent(
                        execution_id=execution_id,
                        eval_item=eval_item,
                        eval_results=evaluation_item_results,
                        success=not agent_execution_output.result.error,
                        agent_output=agent_output,
                        agent_execution_time=agent_execution_output.execution_time,
                        spans=agent_execution_output.spans,
                        logs=agent_execution_output.logs,
                        exception_details=exception_details,
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
                    if eval_run_updated_event.exception_details:
                        eval_run_updated_event.exception_details.exception = (
                            e.root_exception
                        )
                        eval_run_updated_event.exception_details.runtime_exception = (
                            True
                        )

                await self.event_bus.publish(
                    EvaluationEvents.UPDATE_EVAL_RUN,
                    eval_run_updated_event,
                    wait_for_completion=False,
                )
            finally:
                clear_execution_context()

            # Configure span with output and metadata
            await configure_evaluation_span(
                span=span,
                evaluation_run_results=evaluation_run_results,
                execution_id=execution_id,
                input_data=eval_item.inputs,
                agent_execution_output=agent_execution_output
                if "agent_execution_output" in locals()
                else None,
            )

            return evaluation_run_results

    async def _generate_input_for_eval(
        self,
        eval_item: EvaluationItem,
    ) -> EvaluationItem:
        """Use LLM to generate a mock input for an evaluation item."""
        expected_output = (
            getattr(eval_item, "evaluation_criterias", None)
            or getattr(eval_item, "expected_output", None)
            or {}
        )
        generated_input = await generate_llm_input(
            eval_item.input_mocking_strategy,
            (await self.get_schema()).input,
            expected_behavior=eval_item.expected_agent_behavior or "",
            expected_output=expected_output,
        )
        updated_eval_item = eval_item.model_copy(update={"inputs": generated_input})
        return updated_eval_item

    def _get_and_clear_execution_data(
        self, execution_id: str
    ) -> tuple[list[ReadableSpan], list[logging.LogRecord]]:
        spans = self.span_exporter.get_spans(execution_id)
        self.span_exporter.clear(execution_id)
        self.span_collector.clear(execution_id)

        logs = self.logs_exporter.get_logs(execution_id)
        self.logs_exporter.clear(execution_id)

        return spans, logs

    async def execute_runtime(
        self,
        eval_item: EvaluationItem,
        execution_id: str,
        input_overrides: dict[str, Any] | None = None,
    ) -> UiPathEvalRunExecutionOutput:
        log_handler = self._setup_execution_logging(execution_id)
        attributes: dict[str, Any] = {
            "evalId": eval_item.id,
            "span_type": "eval",
            "uipath.custom_instrumentation": True,
        }

        # Create a new runtime with runtime_id for this eval execution.
        # Use eval_item.id to maintain consistent thread_id across suspend and resume.
        # This ensures checkpoints can be found when resuming from suspended state.
        runtime_id = eval_item.id

        eval_runtime = None
        try:
            eval_runtime = await self.factory.new_runtime(
                entrypoint=self.context.entrypoint or "",
                runtime_id=runtime_id,
            )
            execution_runtime = UiPathExecutionRuntime(
                delegate=eval_runtime,
                trace_manager=self.trace_manager,
                log_handler=log_handler,
                execution_id=execution_id,
                span_attributes=attributes,
            )

            start_time = time()
            try:
                # Apply input overrides to inputs if configured
                inputs_with_overrides = apply_input_overrides(
                    eval_item.inputs,
                    input_overrides or {},
                    eval_id=eval_item.id,
                )

                # todo: map eval input type to this type
                # inputs_with_overrides = {
                #     "messages": [
                #         {
                #             "messageId": "E6928DF4-AA36-46BE-B4FC-52ADA2B636D0",
                #             "role": "user",
                #             "contentParts": [
                #                 {
                #                     "contentPartId": "E75CBEA6-7A2C-442B-B0B6-39FFBF17E986",
                #                     "mimeType": "text/plain",
                #                     "data": {"inline": "Hi what can you do"},
                #                     "citations": [],
                #                     "createdAt": "2026-01-18T05:32:39.620Z",
                #                     "updatedAt": "2026-01-18T05:32:39.620Z",
                #                 }
                #             ],
                #             "toolCalls": [],
                #             "interrupts": [],
                #             "spanId": "0f32ee22-0def-4906-9cde-dbb9860c050f",
                #             "createdAt": "2026-01-18T05:32:38.807Z",
                #             "updatedAt": "2026-01-18T05:32:38.807Z",
                #         }
                #     ]
                # }

                # In resume mode, pass None as input
                # The UiPathResumableRuntime wrapper will automatically:
                # 1. Fetch triggers from storage
                # 2. Read resume data via trigger_manager.read_trigger()
                # 3. Build resume map: {interrupt_id: resume_data}
                # 4. Pass this map to the delegate runtime
                if self.context.resume:
                    logger.info(f"Resuming evaluation {eval_item.id}")
                    input = input_overrides if self.context.job_id is None else None
                else:
                    input = inputs_with_overrides

                # Always pass UiPathExecuteOptions explicitly for consistency with debug flow
                options = UiPathExecuteOptions(resume=self.context.resume)
                result = await execution_runtime.execute(
                    input=input,
                    options=options,
                )

                # Log suspend status if applicable
                if result.status == UiPathRuntimeStatus.SUSPENDED:
                    logger.info(f"Evaluation {eval_item.id} suspended")

            except Exception as e:
                end_time = time()
                spans, logs = self._get_and_clear_execution_data(execution_id)

                raise EvaluationRuntimeException(
                    spans=spans,
                    logs=logs,
                    root_exception=e,
                    execution_time=end_time - start_time,
                ) from e

            end_time = time()
            spans, logs = self._get_and_clear_execution_data(execution_id)

            if result is None:
                raise ValueError("Execution result cannot be None for eval runs")
            
            if result is None:
                raise ValueError("Execution result cannot be None for eval runs")

            schema = await self.get_schema()
            is_conversational = False
        
            if schema.metadata and isinstance(schema.metadata, dict):
                engine = schema.metadata.get("settings").get("engine")
                is_conversational = "conversational" in engine

            # print("result.output: " + str(result.output))
            if is_conversational and result.output:
                converted_output = to_conversational_eval_output_schema(result.output.get("messages"))
                print("converted_output: " + str(converted_output))
                result = UiPathRuntimeResult(
                    output=converted_output,
                    status=result.status,
                    error=result.error,
                    trigger=result.trigger,
                    triggers=result.triggers,
                )

            print("result: " + str(result))

            return UiPathEvalRunExecutionOutput(
                execution_time=end_time - start_time,
                spans=spans,
                logs=logs,
                result=result,
            )
        finally:
            if eval_runtime is not None:
                await eval_runtime.dispose()

    def _setup_execution_logging(
        self, eval_item_id: str
    ) -> UiPathRuntimeExecutionLogHandler:
        execution_log_handler = UiPathRuntimeExecutionLogHandler(eval_item_id)
        self.logs_exporter.register(eval_item_id, execution_log_handler)
        return execution_log_handler

    async def run_evaluator(
        self,
        evaluator: GenericBaseEvaluator[Any, Any, Any],
        execution_output: UiPathEvalRunExecutionOutput,
        eval_item: EvaluationItem,
        *,
        evaluation_criteria: Any,
    ) -> EvaluationResult:
        # Create span for evaluator execution
        # Use tracer from trace_manager's provider to ensure spans go through
        # the ExecutionSpanProcessor
        tracer = self.trace_manager.tracer_provider.get_tracer(__name__)
        with tracer.start_as_current_span(
            f"Evaluator: {evaluator.name}",
            attributes={
                "span_type": "evaluator",
                "evaluator_id": evaluator.id,
                "evaluator_name": evaluator.name,
                "eval_item_id": eval_item.id,
                "uipath.custom_instrumentation": True,
            },
        ):
            output_data: dict[str, Any] | str = {}
            if execution_output.result.output:
                if isinstance(execution_output.result.output, BaseModel):
                    output_data = execution_output.result.output.model_dump()
                else:
                    output_data = execution_output.result.output

            agent_execution = AgentExecution(
                agent_input=eval_item.inputs,
                agent_output=output_data,
                agent_trace=execution_output.spans,
                expected_agent_behavior=eval_item.expected_agent_behavior,
            )

            result = await evaluator.validate_and_evaluate_criteria(
                agent_execution=agent_execution,
                evaluation_criteria=evaluation_criteria,
            )

            # Create "Evaluation output" child span with the result
            eval_output_attrs: dict[str, Any] = {
                "span.type": "evalOutput",
                "openinference.span.kind": "CHAIN",
                "value": result.score,
                "evaluatorId": evaluator.id,
                "uipath.custom_instrumentation": True,
            }

            # Add justification if available
            justification = None
            if result.details:
                if isinstance(result.details, BaseModel):
                    details_dict = result.details.model_dump()
                    justification = details_dict.get(
                        "justification", json.dumps(details_dict)
                    )
                else:
                    justification = str(result.details)
                eval_output_attrs["justification"] = justification

            with tracer.start_as_current_span(
                "Evaluation output",
                attributes=eval_output_attrs,
            ) as span:
                # Set output using utility function
                set_evaluation_output_span_output(
                    span=span,
                    score=result.score,
                    evaluator_id=evaluator.id,
                    justification=justification,
                )

            return result

    async def _restore_parent_span(
        self, span_key: str, span_type: str
    ) -> NonRecordingSpan | None:
        """Restore parent span from storage during resume.

        Creates a NonRecordingSpan from saved span context to continue the trace
        across job boundaries without creating duplicate spans.

        Args:
            span_key: Storage key for the span. Examples:
                - "eval_set_run" (string literal) for Evaluation Set Run span
                - eval_item.id (e.g., "eval-001") for individual Evaluation span
            span_type: Human-readable span type for logging (e.g., "Evaluation Set Run")

        Returns:
            NonRecordingSpan if context was restored successfully, None otherwise
        """
        if not self.context.resume:
            return None

        saved_context = await self._get_saved_parent_span_context(span_key)
        if not saved_context:
            return None

        try:
            trace_id = int(saved_context["trace_id"], 16)
            span_id = int(saved_context["span_id"], 16)
            span_context = SpanContext(
                trace_id=trace_id,
                span_id=span_id,
                is_remote=True,
                trace_flags=TraceFlags(0x01),  # Sampled
            )
            parent_span = NonRecordingSpan(span_context)
            logger.info(
                f"EVAL RUNTIME: Restored {span_type} span context for resume - "
                f"trace_id={saved_context['trace_id']}, span_id={saved_context['span_id']}"
            )
            return parent_span
        except Exception as e:
            logger.warning(
                f"EVAL RUNTIME: Failed to restore {span_type} span context: {e}"
            )
            return None

    async def _save_span_context_for_resume(
        self, span: Any, span_key: str, span_type: str
    ) -> None:
        """Save span context for retrieval during resume.

        Extracts trace_id and span_id from the span and persists them to storage
        so they can be restored after suspend/resume across job boundaries.

        Args:
            span: The OpenTelemetry span to save context from
            span_key: Storage key for the span. Examples:
                - "eval_set_run" (string literal) for Evaluation Set Run span
                - eval_item.id (e.g., "eval-001") for individual Evaluation span
            span_type: Human-readable span type for logging (e.g., "Evaluation")
        """
        if span is None or not hasattr(span, "get_span_context"):
            return

        span_context = span.get_span_context()
        span_id_hex = format(span_context.span_id, "016x")
        trace_id_hex = format(span_context.trace_id, "032x")

        await self._save_parent_span_context(
            span_key,
            {
                "span_id": span_id_hex,
                "trace_id": trace_id_hex,
            },
        )

        logger.info(
            f"EVAL RUNTIME: Saved {span_type} span context for resume - "
            f"trace_id={trace_id_hex}, span_id={span_id_hex}"
        )

    async def _save_parent_span_context(
        self, span_key: str, span_context: dict[str, str]
    ) -> None:
        """Save parent span context for retrieval during resume.

        Uses storage protocol from runtime factory to persist span context
        across job boundaries (suspend/resume).

        Storage structure:
            - runtime_id: self.execution_id (eval set run ID)
            - namespace: "eval_parent_span"
            - key: span_key parameter (span-specific identifier)

        Args:
            span_key: Storage key for the span. Can be:
                - "eval_set_run" for Evaluation Set Run span
                - eval_item.id for individual Evaluation spans
            span_context: Dictionary with 'span_id' and 'trace_id' keys (hex strings)
        """
        if self._storage is not None:
            await self._storage.set_value(
                runtime_id=self.execution_id,
                namespace="eval_parent_span",
                key=span_key,
                value=span_context,
            )
            logger.debug(
                f"Saved parent span context to storage for span_key={span_key}: {span_context}"
            )
        else:
            logger.warning(
                f"No storage available, cannot persist parent span context for span_key={span_key}"
            )

    async def _get_saved_parent_span_context(
        self, span_key: str
    ) -> dict[str, str] | None:
        """Retrieve saved parent span context for resume.

        Uses storage protocol from runtime factory to retrieve span context
        persisted during suspend.

        Storage lookup:
            - runtime_id: self.execution_id (eval set run ID)
            - namespace: "eval_parent_span"
            - key: span_key parameter (span-specific identifier)

        Args:
            span_key: Storage key for the span. Can be:
                - "eval_set_run" for Evaluation Set Run span
                - eval_item.id for individual Evaluation spans

        Returns:
            Dictionary with 'span_id' and 'trace_id' keys (hex strings), or None if not found
        """
        if self._storage is not None:
            context = await self._storage.get_value(
                runtime_id=self.execution_id,
                namespace="eval_parent_span",
                key=span_key,
            )
            if context:
                logger.debug(
                    f"Retrieved parent span context from storage for span_key={span_key}: {context}"
                )
            else:
                logger.debug(
                    f"No saved parent span context found in storage for span_key={span_key}"
                )
            return context
        else:
            logger.warning(
                f"No storage available, cannot retrieve parent span context for span_key={span_key}"
            )
            return None

    async def cleanup(self) -> None:
        """Cleanup runtime resources."""
        pass

    async def validate(self) -> None:
        """Cleanup runtime resources."""
        pass
