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

from ._runtime import ExecutionSpanExporter, UiPathEvalContext


class ParallelEvalExecutor(Generic[T, C]):
    """Executor for running evaluations in parallel batches."""

    def __init__(
        self,
        max_workers: int,
        factory: UiPathRuntimeFactory[T, C],
        event_bus: EventBus,
        context: UiPathEvalContext,
        evaluators: List[BaseEvaluator[Any]],
        span_exporter: ExecutionSpanExporter,
    ):
        self.max_workers = max_workers
        self.factory = factory
        self.event_bus = event_bus
        self.context = context
        self.evaluators = evaluators
        self.span_exporter = span_exporter
        self.semaphore = asyncio.Semaphore(max_workers)

    async def execute_parallel(self, evaluation_set: EvaluationSet) -> UiPathEvalOutput:
        """Execute evaluations in parallel batches."""

        tasks = []
        for eval_item in evaluation_set.evaluations:
            task = asyncio.create_task(self._execute_eval_with_semaphore(eval_item))
            tasks.append(task)

        try:
            eval_results = await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            raise ValueError(
                f"Error executing and gathering parallel evaluations: {str(e)}"
            ) from e

        all_results = []

        for i, result in enumerate(eval_results):
            if isinstance(result, Exception):
                print(f"Eval {i} failed with error: {result}")
                continue
            if result:
                all_results.extend(result)

        results = UiPathEvalOutput(
            evaluation_set_name=evaluation_set.name,
            score=0,
            evaluation_set_results=all_results,
        )
        results.compute_average_score()
        return results

    async def _execute_eval_with_semaphore(
        self, eval_item: EvaluationItem
    ) -> EvaluationRunResult:
        """Execute a batch with semaphore control."""
        async with self.semaphore:
            return await self._execute_eval_item(eval_item)

    async def _execute_eval_item(
        self, eval_item: EvaluationItem
    ) -> EvaluationRunResult:
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

            return evaluation_run_result

        except Exception as e:
            print(f"Error executing evaluation {eval_item.name}: {str(e)}")

            failed_result = EvaluationRunResult(
                evaluation_name=eval_item.name, evaluation_run_results=[]
            )
            failed_result.score = 0.0
            return failed_result

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
