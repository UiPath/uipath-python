import json
import logging
import uuid
from collections import defaultdict
from contextlib import contextmanager
from pathlib import Path
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
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from opentelemetry.trace import Status, StatusCode
from pydantic import BaseModel
from uipath.core.tracing import UiPathTraceManager
from uipath.core.tracing.processors import UiPathExecutionBatchTraceProcessor
from uipath.runtime import (
    UiPathExecutionRuntime,
    UiPathRuntimeFactoryProtocol,
    UiPathRuntimeProtocol,
    UiPathRuntimeResult,
    UiPathRuntimeStatus,
)
from uipath.runtime.errors import (
    UiPathErrorCategory,
    UiPathErrorContract,
)
from uipath.runtime.logging import UiPathRuntimeExecutionLogHandler
from uipath.runtime.schema import UiPathRuntimeSchema

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
from ...eval.evaluators import BaseEvaluator
from ...eval.models import EvaluationResult
from ...eval.models.models import AgentExecution, EvalItemResult
from .._utils._eval_set import EvalHelpers
from .._utils._parallelization import execute_parallel
from ._configurable_factory import ConfigurableRuntimeFactory
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

    entrypoint: str | None = None
    no_report: bool | None = False
    workers: int | None = 1
    eval_set: str | None = None
    eval_ids: list[str] | None = None
    eval_set_run_id: str | None = None
    verbose: bool = False
    enable_mocker_cache: bool = False
    report_coverage: bool = False
    model_settings_id: str = "default"


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
        # Wrap the factory to support model settings overrides
        self.factory = ConfigurableRuntimeFactory(factory)
        self.event_bus: EventBus = event_bus
        self.trace_manager: UiPathTraceManager = trace_manager
        self.span_exporter: ExecutionSpanExporter = ExecutionSpanExporter()
        self.span_collector: ExecutionSpanCollector = ExecutionSpanCollector()

        # Span processor feeds both exporter and collector
        span_processor = ExecutionSpanProcessor(self.span_exporter, self.span_collector)
        self.trace_manager.tracer_span_processors.append(span_processor)
        self.trace_manager.tracer_provider.add_span_processor(span_processor)

        self.logs_exporter: ExecutionLogsExporter = ExecutionLogsExporter()
        self.execution_id = str(uuid.uuid4())
        self.coverage = coverage.Coverage(branch=True)

    async def __aenter__(self) -> "UiPathEvalRuntime":
        if self.context.report_coverage:
            self.coverage.start()
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self.context.report_coverage:
            self.coverage.stop()
            self.coverage.report(include=["./*"], show_missing=True)

        # Clean up any temporary files created by the factory
        if hasattr(self.factory, "dispose"):
            await self.factory.dispose()

    async def get_schema(self, runtime: UiPathRuntimeProtocol) -> UiPathRuntimeSchema:
        schema = await runtime.get_schema()
        if schema is None:
            raise ValueError("Schema could not be loaded")
        return schema

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
        runtime: UiPathRuntimeProtocol,
    ) -> Tuple[
        EvaluationSet,
        list[BaseEvaluator[Any, Any, Any]],
        Iterable[Awaitable[EvaluationRunResult]],
    ]:
        if self.context.eval_set is None:
            raise ValueError("eval_set must be provided for evaluation runs")

        # Load eval set (path is already resolved in cli_eval.py)
        evaluation_set, _ = EvalHelpers.load_eval_set(
            self.context.eval_set, self.context.eval_ids
        )
        evaluators = await self._load_evaluators(evaluation_set, runtime)

        await self.event_bus.publish(
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

        return (
            evaluation_set,
            evaluators,
            (
                self._execute_eval(eval_item, evaluators, runtime)
                for eval_item in evaluation_set.evaluations
            ),
        )

    async def execute(self) -> UiPathRuntimeResult:
        # Configure model settings override before creating runtime
        await self._configure_model_settings_override()

        runtime = await self.factory.new_runtime(
            entrypoint=self.context.entrypoint or "",
            runtime_id=self.execution_id,
        )
        try:
            with self._mocker_cache():
                # Create the parent "Evaluation set run" span
                # Use tracer from trace_manager's provider to ensure spans go through
                # the ExecutionSpanProcessor
                # NOTE: Do NOT set execution.id on this parent span, as the mixin in
                # UiPathExecutionBatchTraceProcessor propagates execution.id from parent
                # to child spans, which would overwrite the per-eval execution.id
                tracer = self.trace_manager.tracer_provider.get_tracer(__name__)
                span_attributes: dict[str, str] = {
                    "span_type": "eval_set_run",
                }
                if self.context.eval_set_run_id:
                    span_attributes["eval_set_run_id"] = self.context.eval_set_run_id
                with tracer.start_as_current_span(
                    "Evaluation Set Run", attributes=span_attributes
                ) as span:
                    try:
                        (
                            evaluation_set,
                            evaluators,
                            evaluation_iterable,
                        ) = await self.initiate_evaluation(runtime)
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
                                evaluator_averages[result_dto.evaluator_id] += (
                                    result_dto.result.score
                                )
                                evaluator_count[result_dto.evaluator_id] += 1

                        for eval_id in evaluator_averages:
                            evaluator_averages[eval_id] = (
                                evaluator_averages[eval_id] / evaluator_count[eval_id]
                            )

                        # Configure span with output and metadata
                        await configure_eval_set_run_span(
                            span=span,
                            evaluator_averages=evaluator_averages,
                            execution_id=self.execution_id,
                            runtime=runtime,
                            get_schema_func=self.get_schema,
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

                        result = UiPathRuntimeResult(
                            output={**results.model_dump(by_alias=True)},
                            status=UiPathRuntimeStatus.SUCCESSFUL,
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
        finally:
            await runtime.dispose()

    async def _execute_eval(
        self,
        eval_item: EvaluationItem,
        evaluators: list[BaseEvaluator[Any, Any, Any]],
        runtime: UiPathRuntimeProtocol,
    ) -> EvaluationRunResult:
        # Generate LLM-based input if input_mocking_strategy is defined
        if eval_item.input_mocking_strategy:
            eval_item = await self._generate_input_for_eval(eval_item, runtime)

        execution_id = str(uuid.uuid4())

        set_execution_context(eval_item, self.span_collector, execution_id)

        await self.event_bus.publish(
            EvaluationEvents.CREATE_EVAL_RUN,
            EvalRunCreatedEvent(
                execution_id=execution_id,
                eval_item=eval_item,
            ),
        )

        # Create the "Evaluation" span for this eval item
        # Use tracer from trace_manager's provider to ensure spans go through
        # the ExecutionSpanProcessor
        tracer = self.trace_manager.tracer_provider.get_tracer(__name__)
        with tracer.start_as_current_span(
            "Evaluation",
            attributes={
                "execution.id": execution_id,
                "span_type": "evaluation",
                "eval_item_id": eval_item.id,
                "eval_item_name": eval_item.name,
            },
        ) as span:
            evaluation_run_results = EvaluationRunResult(
                evaluation_name=eval_item.name, evaluation_run_results=[]
            )

            try:
                try:
                    agent_execution_output = await self.execute_runtime(
                        eval_item, execution_id, runtime
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
        self, eval_item: EvaluationItem, runtime: UiPathRuntimeProtocol
    ) -> EvaluationItem:
        """Use LLM to generate a mock input for an evaluation item."""
        generated_input = await generate_llm_input(
            eval_item, (await self.get_schema(runtime)).input
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

    async def _configure_model_settings_override(self) -> None:
        """Configure the factory with model settings override if specified."""
        # Skip if no model settings ID specified
        if (
            not self.context.model_settings_id
            or self.context.model_settings_id == "default"
        ):
            return

        # Load evaluation set to get model settings
        evaluation_set, _ = EvalHelpers.load_eval_set(self.context.eval_set or "")
        if (
            not hasattr(evaluation_set, "model_settings")
            or not evaluation_set.model_settings
        ):
            logger.warning("No model settings available in evaluation set")
            return

        # Find the specified model settings
        target_model_settings = next(
            (
                ms
                for ms in evaluation_set.model_settings
                if ms.id == self.context.model_settings_id
            ),
            None,
        )

        if not target_model_settings:
            logger.warning(
                f"Model settings ID '{self.context.model_settings_id}' not found in evaluation set"
            )
            return

        logger.info(
            f"Configuring model settings override: id='{target_model_settings.id}', "
            f"model_name='{target_model_settings.model_name}', temperature='{target_model_settings.temperature}'"
        )

        # Configure the factory with the override settings
        self.factory.set_model_settings_override(target_model_settings)

    async def execute_runtime(
        self,
        eval_item: EvaluationItem,
        execution_id: str,
        runtime: UiPathRuntimeProtocol,
    ) -> UiPathEvalRunExecutionOutput:
        log_handler = self._setup_execution_logging(execution_id)
        attributes = {
            "evalId": eval_item.id,
            "span_type": "eval",
        }

        # Create a new runtime with unique runtime_id for this eval execution.
        # This ensures each eval has its own LangGraph thread_id (clean state),
        # preventing message accumulation across eval runs.
        eval_runtime = None
        try:
            eval_runtime = await self.factory.new_runtime(
                entrypoint=self.context.entrypoint or "",
                runtime_id=execution_id,
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
                result = await execution_runtime.execute(
                    input=eval_item.inputs,
                )
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
        evaluator: BaseEvaluator[Any, Any, Any],
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

    async def _get_agent_model(self, runtime: UiPathRuntimeProtocol) -> str | None:
        """Get agent model from the runtime.

        Returns:
            The model name from agent settings, or None if not found.
        """
        try:
            model = self._find_agent_model_in_runtime(runtime)
            if model:
                logger.debug(f"Got agent model from runtime: {model}")
            return model
        except Exception:
            return None

    def _find_agent_model_in_runtime(
        self, runtime: UiPathRuntimeProtocol
    ) -> str | None:
        """Recursively search for get_agent_model in runtime and its delegates.

        Runtimes may be wrapped (e.g., ResumableRuntime wraps TelemetryWrapper
        which wraps the base runtime). This method traverses the wrapper chain
        to find a runtime that implements LLMAgentRuntimeProtocol.

        Args:
            runtime: The runtime to check (may be a wrapper)

        Returns:
            The model name if found, None otherwise.
        """
        # Check if this runtime implements the protocol
        if isinstance(runtime, LLMAgentRuntimeProtocol):
            return runtime.get_agent_model()

        # Check for delegate property (used by UiPathResumableRuntime, TelemetryRuntimeWrapper)
        delegate = getattr(runtime, "delegate", None) or getattr(
            runtime, "_delegate", None
        )
        if delegate is not None:
            return self._find_agent_model_in_runtime(delegate)

        return None

    async def _load_evaluators(
        self, evaluation_set: EvaluationSet, runtime: UiPathRuntimeProtocol
    ) -> list[BaseEvaluator[Any, Any, Any]]:
        """Load evaluators referenced by the evaluation set."""
        evaluators = []
        eval_set = self.context.eval_set
        if eval_set is None:
            raise ValueError("eval_set cannot be None")
        evaluators_dir = Path(eval_set).parent.parent / "evaluators"

        # Load agent model for 'same-as-agent' resolution in legacy evaluators
        agent_model = await self._get_agent_model(runtime)

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
                    evaluator = EvaluatorFactory.create_evaluator(
                        data, evaluators_dir, agent_model=agent_model
                    )
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
