"""Strategy pattern for evaluation execution.

Decouples how evaluators are run from the evaluation runtime, allowing
local execution (current behavior) or remote execution via the Agents backend.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Protocol

from pydantic import BaseModel

from uipath.eval.models.models import AgentExecution, EvalItemResult, EvaluationResult, ScoreType

if TYPE_CHECKING:
    from uipath._cli._evals._models._evaluation_set import EvaluationItem
    from uipath._cli._evals._models._output import (
        EvaluationResultDto,
        EvaluationRunResultDto,
        UiPathEvalRunExecutionOutput,
    )
    from uipath._cli._evals._remote_evaluator import (
        RemoteEvaluationClient,
        RemoteEvaluationStatusResponse,
    )
    from uipath.eval.evaluators.base_evaluator import GenericBaseEvaluator

logger = logging.getLogger(__name__)


class EvaluationStrategy(Protocol):
    """Protocol for evaluation execution strategies."""

    async def evaluate(
        self,
        eval_item: EvaluationItem,
        evaluators: list[GenericBaseEvaluator[Any, Any, Any]],
        execution_output: UiPathEvalRunExecutionOutput,
        run_evaluator_fn: Any,
    ) -> list[EvalItemResult]:
        """Run evaluators against an agent execution output.

        Args:
            eval_item: The evaluation item being evaluated.
            evaluators: List of evaluator instances to run.
            execution_output: The agent execution output to evaluate.
            run_evaluator_fn: Async callable to run a single evaluator
                (signature matches UiPathEvalRuntime.run_evaluator).

        Returns:
            List of evaluation item results.
        """
        ...


class LocalEvaluationStrategy:
    """Runs evaluators locally in the CLI process.

    This is the default strategy that preserves the existing behavior
    where evaluators execute in the same process as the agent.
    """

    async def evaluate(
        self,
        eval_item: EvaluationItem,
        evaluators: list[GenericBaseEvaluator[Any, Any, Any]],
        execution_output: UiPathEvalRunExecutionOutput,
        run_evaluator_fn: Any,
    ) -> list[EvalItemResult]:
        evaluation_item_results: list[EvalItemResult] = []

        for evaluator in evaluators:
            if evaluator.id not in eval_item.evaluation_criterias:
                continue

            evaluation_criteria = eval_item.evaluation_criterias[evaluator.id]

            evaluation_result = await run_evaluator_fn(
                evaluator=evaluator,
                execution_output=execution_output,
                eval_item=eval_item,
                evaluation_criteria=evaluator.evaluation_criteria_type(
                    **evaluation_criteria
                )
                if evaluation_criteria
                else None,
            )

            evaluation_item_results.append(
                EvalItemResult(
                    evaluator_id=evaluator.id,
                    result=evaluation_result,
                )
            )

        return evaluation_item_results


class RemoteEvaluationStrategy:
    """Submits evaluations to the remote C# Agents backend.

    The backend runs evaluators via Temporal workflows and reports results
    to Studio Web. The CLI only needs to poll for results.
    """

    def __init__(
        self,
        client: RemoteEvaluationClient,
        eval_set_run_id: str,
        eval_set_id: str,
        project_id: str,
        entrypoint: str = "",
        is_coded: bool = True,
        report_to_studio_web: bool = True,
    ):
        self._client = client
        self._eval_set_run_id = eval_set_run_id
        self._eval_set_id = eval_set_id
        self._project_id = project_id
        self._entrypoint = entrypoint
        self._is_coded = is_coded
        self._report_to_studio_web = report_to_studio_web

    async def evaluate(
        self,
        eval_item: EvaluationItem,
        evaluators: list[GenericBaseEvaluator[Any, Any, Any]],
        execution_output: UiPathEvalRunExecutionOutput,
        run_evaluator_fn: Any,
    ) -> list[EvalItemResult]:
        from uipath._cli._evals._remote_evaluator import (
            EvaluationItemPayload,
            EvaluatorConfigPayload,
            RemoteEvaluationRequest,
            RemoteJobStatus,
        )
        from uipath.eval.models.models import (
            BooleanEvaluationResult,
            ErrorEvaluationResult,
            NumericEvaluationResult,
        )
        from uipath.eval.models.serializable_span import SerializableSpan

        # Check for custom file:// evaluators — these can't run remotely
        from uipath._utils.constants import CUSTOM_EVALUATOR_PREFIX

        has_custom = False
        for evaluator in evaluators:
            if evaluator.id not in eval_item.evaluation_criterias:
                continue
            evaluator_schema = getattr(evaluator, "evaluator_schema", "") or ""
            if isinstance(evaluator_schema, str) and evaluator_schema.startswith(
                CUSTOM_EVALUATOR_PREFIX
            ):
                has_custom = True
                break

        if has_custom:
            logger.warning(
                f"Eval item '{eval_item.name}' has custom file:// evaluators. "
                "Falling back to local evaluation."
            )
            local = LocalEvaluationStrategy()
            return await local.evaluate(
                eval_item, evaluators, execution_output, run_evaluator_fn
            )

        # Serialize traces
        serialized_traces = []
        for span in execution_output.spans:
            try:
                serialized_traces.append(SerializableSpan.from_readable_span(span))
            except Exception as e:
                logger.warning(f"Skipping span serialization error: {e}")

        # Build agent output
        agent_output: dict[str, Any] | str = {}
        if execution_output.result.output:
            if isinstance(execution_output.result.output, BaseModel):
                agent_output = execution_output.result.output.model_dump()
            else:
                agent_output = execution_output.result.output

        # Build evaluator configs
        evaluator_configs = []
        for evaluator in evaluators:
            if evaluator.id not in eval_item.evaluation_criterias:
                continue
            evaluator_configs.append(
                EvaluatorConfigPayload(
                    id=evaluator.id,
                    version=getattr(evaluator, "version", "1.0") or "1.0",
                    evaluatorTypeId=getattr(evaluator, "evaluator_type_id", evaluator.id),
                    evaluatorConfig=getattr(evaluator, "evaluator_config", {}) or {},
                    evaluatorSchema=getattr(evaluator, "evaluator_schema", "") or "",
                )
            )

        # Build evaluation item payload
        agent_error = None
        if execution_output.result.error:
            agent_error = str(execution_output.result.error.detail)

        evaluation_item_payload = EvaluationItemPayload(
            id=eval_item.id,
            name=eval_item.name,
            inputs=eval_item.inputs,
            evaluationCriterias=eval_item.evaluation_criterias,
            expectedAgentBehavior=eval_item.expected_agent_behavior,
            agentOutput=agent_output,
            agentExecutionTime=execution_output.execution_time,
            serializedTraces=serialized_traces,
            agentError=agent_error,
        )

        # Submit to remote backend
        request = RemoteEvaluationRequest(
            evalSetRunId=self._eval_set_run_id,
            evalSetId=self._eval_set_id,
            projectId=self._project_id,
            entrypoint=self._entrypoint,
            isCoded=self._is_coded,
            reportToStudioWeb=self._report_to_studio_web,
            evaluatorConfigs=evaluator_configs,
            evaluationItems=[evaluation_item_payload],
        )

        try:
            submit_response = await self._client.submit_evaluation(request)
            status_response = await self._client.poll_status(
                submit_response.evaluation_job_id
            )
        except Exception as e:
            logger.warning(
                f"Remote evaluation failed for '{eval_item.name}': {e}. "
                "Falling back to local evaluation."
            )
            local = LocalEvaluationStrategy()
            return await local.evaluate(
                eval_item, evaluators, execution_output, run_evaluator_fn
            )

        # Convert remote results to EvalItemResult list
        return _convert_remote_results(status_response, eval_item.id)


def _convert_remote_results(
    status_response: RemoteEvaluationStatusResponse,
    eval_item_id: str,
) -> list[EvalItemResult]:
    """Convert remote evaluation results to local EvalItemResult format."""
    from uipath._cli._evals._remote_evaluator import RemoteJobStatus
    from uipath.eval.models.models import (
        BooleanEvaluationResult,
        ErrorEvaluationResult,
        NumericEvaluationResult,
    )

    results: list[EvalItemResult] = []

    # Find results for this eval item
    for item_result in status_response.results:
        if item_result.evaluation_item_id != eval_item_id:
            continue

        for evaluator_result in item_result.evaluator_results:
            score_type = ScoreType(evaluator_result.score_type)

            evaluation_result: EvaluationResult
            if score_type == ScoreType.BOOLEAN:
                evaluation_result = BooleanEvaluationResult(
                    score=bool(evaluator_result.score),
                    details=evaluator_result.details,
                    evaluation_time=evaluator_result.evaluation_time,
                )
            elif score_type == ScoreType.ERROR:
                evaluation_result = ErrorEvaluationResult(
                    score=evaluator_result.score,
                    details=evaluator_result.details,
                    evaluation_time=evaluator_result.evaluation_time,
                )
            else:
                evaluation_result = NumericEvaluationResult(
                    score=evaluator_result.score,
                    details=evaluator_result.details,
                    evaluation_time=evaluator_result.evaluation_time,
                )

            results.append(
                EvalItemResult(
                    evaluator_id=evaluator_result.evaluator_id,
                    result=evaluation_result,
                )
            )

    return results
