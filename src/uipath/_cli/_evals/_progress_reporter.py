"""Progress reporter for sending evaluation updates to StudioWeb."""

import functools
import json
import logging
import os
from typing import Any, List

from uipath import UiPath
from uipath._cli._evals._models._evaluation_set import EvaluationItem, EvaluationStatus
from uipath._cli._evals._models._sw_reporting import AgentSnapshot, SwProgressItem
from uipath._cli._utils._console import ConsoleLogger
from uipath._utils import Endpoint, RequestSpec
from uipath._utils.constants import ENV_TENANT_ID, HEADER_INTERNAL_TENANT_ID
from uipath.eval.evaluators import BaseEvaluator
from uipath.eval.models import EvalItemResult


def gracefully_handle_errors(func):
    """Decorator to catch and log errors without stopping execution."""

    @functools.wraps(func)
    async def wrapper(self, *args, **kwargs):
        try:
            return await func(self, *args, **kwargs)
        except Exception as e:
            if hasattr(self, "_console"):
                error_type = type(e).__name__
                self._console.warning(
                    f"Cannot report progress to SW. "
                    f"Function: {func.__name__}, "
                    f"Error type: {error_type}, "
                    f"Details: {e}"
                )
            return None

    return wrapper


class StudioWebProgressReporter:
    """Handles reporting evaluation progress to StudioWeb."""

    def __init__(self):
        logging.getLogger("uipath._cli.middlewares").setLevel(logging.CRITICAL)
        console_logger = ConsoleLogger.get_instance()
        uipath = UiPath()

        self._client = uipath.api_client
        self._console = console_logger
        self._project_id = os.getenv("UIPATH_PROJECT_ID", None)
        if not self._project_id:
            self._console.warning(
                "Cannot report data to StudioWeb. Please set UIPATH_PROJECT_ID."
            )

    @gracefully_handle_errors
    async def create_eval_set_run(
        self,
        eval_set_id: str,
        agent_snapshot: AgentSnapshot,
        no_of_evals: int,
        evaluators: List[BaseEvaluator[Any]],
    ) -> str:
        """Create a new evaluation set run in StudioWeb."""
        spec = self._create_eval_set_run_spec(eval_set_id, agent_snapshot, no_of_evals)
        response = await self._client.request_async(
            method=spec.method,
            url=spec.endpoint,
            params=spec.params,
            json=spec.json,
            headers=spec.headers,
        )
        eval_set_run_id = json.loads(response.content)["id"]
        return eval_set_run_id

    @gracefully_handle_errors
    async def create_eval_run(
        self, eval_item: EvaluationItem, eval_set_run_id: str
    ) -> str:
        """Create a new evaluation run in StudioWeb.

        Args:
            eval_item: Dictionary containing evaluation data
            eval_set_run_id: The ID of the evaluation set run

        Returns:
            The ID of the created evaluation run
        """
        spec = self._create_eval_run_spec(eval_item, eval_set_run_id)
        response = await self._client.request_async(
            method=spec.method,
            url=spec.endpoint,
            params=spec.params,
            json=spec.json,
            headers=spec.headers,
        )
        return json.loads(response.content)["id"]

    @gracefully_handle_errors
    async def update_eval_run(
        self,
        sw_progress_item: SwProgressItem,
        evaluators: dict[str, BaseEvaluator[Any]],
    ):
        """Update an evaluation run with results."""
        assertion_runs, evaluator_scores = self._collect_results(
            sw_progress_item.eval_results, evaluators
        )
        spec = self._update_eval_run_spec(
            assertion_runs=assertion_runs,
            evaluator_scores=evaluator_scores,
            eval_run_id=sw_progress_item.eval_run_id,
            execution_time=sw_progress_item.agent_execution_time,
            actual_output=sw_progress_item.agent_output,
        )
        await self._client.request_async(
            method=spec.method,
            url=spec.endpoint,
            params=spec.params,
            json=spec.json,
            headers=spec.headers,
        )

    @gracefully_handle_errors
    async def update_eval_set_run(
        self,
        eval_set_run_id: str,
        evaluator_scores: dict[str, list[float]],
        evaluators: dict[str, BaseEvaluator[Any]],
    ):
        """Update the evaluation set run status to complete."""
        spec = self._update_eval_set_run_spec(
            eval_set_run_id, evaluator_scores, evaluators
        )
        await self._client.request_async(
            method=spec.method,
            url=spec.endpoint,
            params=spec.params,
            json=spec.json,
            headers=spec.headers,
        )

    def _collect_results(
        self,
        eval_results: list[EvalItemResult],
        evaluators: dict[str, BaseEvaluator[Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        assertion_runs: list[dict[str, Any]] = []
        evaluator_scores_list: list[dict[str, Any]] = []
        for eval_result in eval_results:
            evaluator_scores_list.append(
                {
                    "type": eval_result.result.score_type.value,
                    "value": eval_result.result.score,
                    "justification": eval_result.result.details,
                    "evaluatorId": eval_result.evaluator_id,
                }
            )
            assertion_runs.append(
                {
                    "status": EvaluationStatus.COMPLETED.value,
                    "evaluatorId": eval_result.evaluator_id,
                    "completionMetrics": {
                        "duration": int(eval_result.result.evaluation_time)
                        if eval_result.result.evaluation_time
                        else 0,
                        "cost": None,
                        "tokens": 0,
                        "completionTokens": 0,
                        "promptTokens": 0,
                    },
                    "assertionSnapshot": {
                        "assertionType": evaluators[
                            eval_result.evaluator_id
                        ].evaluator_type.name,
                        "outputKey": evaluators[
                            eval_result.evaluator_id
                        ].target_output_key,
                    },
                }
            )
        return assertion_runs, evaluator_scores_list

    def _update_eval_run_spec(
        self,
        assertion_runs: list[dict[str, Any]],
        evaluator_scores: list[dict[str, Any]],
        eval_run_id: str,
        actual_output: dict[str, Any],
        execution_time: float,
    ) -> RequestSpec:
        return RequestSpec(
            method="PUT",
            endpoint=Endpoint(
                f"agentsruntime_/api/execution/agents/{self._project_id}/evalRun"
            ),
            json={
                "evalRunId": eval_run_id,
                "status": EvaluationStatus.COMPLETED.value,
                "result": {
                    "output": {"content": {**actual_output}},
                    "evaluatorScores": evaluator_scores,
                },
                "completionMetrics": {"duration": int(execution_time)},
                "assertionRuns": assertion_runs,
            },
            headers=self._tenant_header(),
        )

    def _create_eval_run_spec(
        self, eval_item: EvaluationItem, eval_set_run_id: str
    ) -> RequestSpec:
        return RequestSpec(
            method="POST",
            endpoint=Endpoint(
                f"agentsruntime_/api/execution/agents/{self._project_id}/evalRun"
            ),
            json={
                "evalSetRunId": eval_set_run_id,
                "evalSnapshot": {
                    "id": eval_item.id,
                    "name": eval_item.name,
                    "inputs": eval_item.inputs,
                    "expectedOutput": eval_item.expected_output,
                },
                "status": EvaluationStatus.IN_PROGRESS.value,
            },
            headers=self._tenant_header(),
        )

    def _create_eval_set_run_spec(
        self,
        eval_set_id: str,
        agent_snapshot: AgentSnapshot,
        no_of_evals: int,
    ) -> RequestSpec:
        return RequestSpec(
            method="POST",
            endpoint=Endpoint(
                f"agentsruntime_/api/execution/agents/{self._project_id}/evalSetRun"
            ),
            json={
                "agentId": self._project_id,
                "evalSetId": eval_set_id,
                "agentSnapshot": agent_snapshot.model_dump(by_alias=True),
                "status": EvaluationStatus.IN_PROGRESS.value,
                "numberOfEvalsExecuted": no_of_evals,
            },
            headers=self._tenant_header(),
        )

    def _compute_evaluator_scores(
        self,
        evaluator_scores: dict[str, list[float]],
        evaluators: dict[str, BaseEvaluator[Any]],
    ):
        evaluator_scores_list = []
        evaluator_averages = []

        for evaluator in evaluators.values():
            scores = evaluator_scores.get(evaluator.id, [])
            if scores:
                avg_score = sum(scores) / len(scores)
                evaluator_scores_list.append(
                    {"value": avg_score, "evaluatorId": evaluator.id}
                )
                evaluator_averages.append(avg_score)
            else:
                evaluator_scores_list.append({"value": 0, "evaluatorId": evaluator.id})
                evaluator_averages.append(0)

        overall_score = (
            sum(evaluator_averages) / len(evaluator_averages)
            if evaluator_averages
            else 0
        )
        return evaluator_scores_list, overall_score

    def _update_eval_set_run_spec(
        self,
        eval_set_run_id: str,
        evaluator_scores: dict[str, list[float]],
        evaluators: dict[str, BaseEvaluator[Any]],
    ) -> RequestSpec:
        evaluator_scores_list, overall_score = self._compute_evaluator_scores(
            evaluator_scores, evaluators
        )
        return RequestSpec(
            method="PUT",
            endpoint=Endpoint(
                f"agentsruntime_/api/execution/agents/{self._project_id}/evalSetRun"
            ),
            json={
                "evalSetRunId": eval_set_run_id,
                "status": EvaluationStatus.COMPLETED.value,
                "evaluatorScores": evaluator_scores_list,
            },
            headers=self._tenant_header(),
        )

    def _tenant_header(self) -> dict[str, str]:
        tenant_id = os.getenv(ENV_TENANT_ID, None)
        if not tenant_id:
            self._console.error(
                f"{ENV_TENANT_ID} env var is not set. Please run 'uipath auth'."
            )
        return {HEADER_INTERNAL_TENANT_ID: tenant_id}  # type: ignore
