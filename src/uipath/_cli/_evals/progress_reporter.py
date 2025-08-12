"""Progress reporter for sending evaluation updates to StudioWeb."""

import json
import logging
import os
from typing import Any, List

from uipath import UiPath
from uipath._cli._evals._evaluators import EvaluatorBase
from uipath._cli._evals._models._evaluation_set import EvaluationStatus
from uipath._cli._evals._models._evaluators import EvalItemResult, ScoreType
from uipath._cli._utils._console import ConsoleLogger
from uipath._utils import Endpoint, RequestSpec
from uipath._utils.constants import ENV_TENANT_ID, HEADER_INTERNAL_TENANT_ID


class ProgressReporter:
    """Handles reporting evaluation progress to StudioWeb via API calls."""

    def __init__(
        self,
        eval_set_id: str,
        agent_snapshot: str,
        no_of_evals: int,
        evaluators: List[EvaluatorBase],
    ):
        """Initialize the progress reporter.

        Args:
            eval_set_id: ID of the evaluation set
            agent_snapshot: JSON snapshot of the agent configuration
            no_of_evals: Number of evaluations in the set
            evaluators: List of evaluator instances
        """
        self._eval_set_id = eval_set_id
        self.agent_snapshot = agent_snapshot
        self._no_of_evals = no_of_evals
        self._evaluators: dict[str, EvaluatorBase] = {
            evaluator.id: evaluator for evaluator in evaluators
        }
        self._evaluator_scores: dict[str, list[float]] = {
            evaluator.id: [] for evaluator in evaluators
        }

        # Disable middleware logging and use the same console as ConsoleLogger
        logging.getLogger("uipath._cli.middlewares").setLevel(logging.CRITICAL)

        console_logger = ConsoleLogger.get_instance()

        uipath = UiPath()

        self._eval_set_run_id = None
        self._client = uipath.api_client
        self._console = console_logger
        self._project_id = os.getenv("UIPATH_PROJECT_ID", None)
        if not self._project_id:
            self._console.warning(
                "Cannot report data to StudioWeb. Please set UIPATH_PROJECT_ID."
            )

    async def create_eval_set_run(self):
        """Create a new evaluation set run in StudioWeb."""
        spec = self._create_eval_set_run_spec()
        response = await self._client.request_async(
            method=spec.method,
            url=spec.endpoint,
            params=spec.params,
            content=spec.content,
            headers=spec.headers,
        )
        self._eval_set_run_id = json.loads(response.content)["id"]

    async def create_eval_run(self, eval_item: dict[str, Any]):
        """Create a new evaluation run in StudioWeb.

        Args:
            eval_item: Dictionary containing evaluation data

        Returns:
            The ID of the created evaluation run
        """
        spec = self._create_eval_run_spec(eval_item)
        response = await self._client.request_async(
            method=spec.method,
            url=spec.endpoint,
            params=spec.params,
            content=spec.content,
            headers=spec.headers,
        )
        return json.loads(response.content)["id"]

    async def update_eval_run(
        self,
        eval_results: list[EvalItemResult],
        eval_run_id: str,
        execution_time: float,
    ):
        """Update an evaluation run with results.

        Args:
            eval_results: Dictionary mapping evaluator IDs to evaluation results
            eval_run_id: ID of the evaluation run to update
            execution_time: The agent execution time
        """
        assertion_runs, evaluator_scores, actual_output = self._collect_results(
            eval_results
        )
        spec = self._update_eval_run_spec(
            assertion_runs=assertion_runs,
            evaluator_scores=evaluator_scores,
            eval_run_id=eval_run_id,
            execution_time=execution_time,
            actual_output=actual_output,
        )
        await self._client.request_async(
            method=spec.method,
            url=spec.endpoint,
            params=spec.params,
            content=spec.content,
            headers=spec.headers,
        )

    async def update_eval_set_run(self):
        """Update the evaluation set run status to complete."""
        spec = self._update_eval_set_run_spec()
        await self._client.request_async(
            method=spec.method,
            url=spec.endpoint,
            params=spec.params,
            content=spec.content,
            headers=spec.headers,
        )

    def _collect_results(
        self, eval_results: list[EvalItemResult]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
        assertion_runs: list[dict[str, Any]] = []
        evaluator_scores: list[dict[str, Any]] = []
        actual_output: dict[str, Any] = {}
        for eval_result in eval_results:
            # keep track of evaluator scores. this should be removed after this computation is done server-side

            # check the evaluator score type
            match eval_result.result.score_type:
                case ScoreType.NUMERICAL:
                    self._evaluator_scores[eval_result.evaluator_id].append(
                        eval_result.result.score
                    )
                case ScoreType.BOOLEAN:
                    self._evaluator_scores[eval_result.evaluator_id].append(
                        100 if eval_result.result.score else 0
                    )
                case ScoreType.ERROR:
                    self._evaluator_scores[eval_result.evaluator_id].append(0)

            evaluator_scores.append(
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
                        "duration": eval_result.result.evaluation_time,
                        "cost": None,
                        "tokens": 0,
                        "completionTokens": 0,
                        "promptTokens": 0,
                    },
                    "assertionSnapshot": {
                        "assertionType": self._evaluators[
                            eval_result.evaluator_id
                        ].type.name,
                        "outputKey": self._evaluators[
                            eval_result.evaluator_id
                        ].target_output_key,
                    },
                }
            )

            # we extract the actual output here. we should have the same 'actual_output' for each 'EvalItemResult'
            actual_output = eval_result.result.actual_output

        return assertion_runs, evaluator_scores, actual_output

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
            content=json.dumps(
                {
                    "evalRunId": eval_run_id,
                    "status": EvaluationStatus.COMPLETED.value,
                    "result": {
                        "output": {"content": {**actual_output}},
                        "evaluatorScores": evaluator_scores,
                    },
                    "completionMetrics": {"duration": int(execution_time)},
                    "assertionRuns": assertion_runs,
                }
            ),
            headers=self._tenant_header(),
        )

    def _create_eval_run_spec(self, eval_item: dict[str, Any]) -> RequestSpec:
        return RequestSpec(
            method="POST",
            endpoint=Endpoint(
                f"agentsruntime_/api/execution/agents/{self._project_id}/evalRun"
            ),
            content=json.dumps(
                {
                    "evalSetRunId": self._eval_set_run_id,
                    "evalSnapshot": {
                        "id": eval_item["id"],
                        "name": eval_item["name"],
                        "inputs": eval_item.get("inputs"),
                        "expectedOutput": eval_item.get("expectedOutput", {}),
                    },
                    "status": EvaluationStatus.IN_PROGRESS.value,
                }
            ),
            headers=self._tenant_header(),
        )

    def _create_eval_set_run_spec(
        self,
    ) -> RequestSpec:
        agent_snapshot_dict = json.loads(self.agent_snapshot)

        return RequestSpec(
            method="POST",
            endpoint=Endpoint(
                f"agentsruntime_/api/execution/agents/{self._project_id}/evalSetRun"
            ),
            content=json.dumps(
                {
                    "agentId": self._project_id,
                    "evalSetId": self._eval_set_id,
                    "agentSnapshot": agent_snapshot_dict,
                    "status": EvaluationStatus.IN_PROGRESS.value,
                    "numberOfEvalsExecuted": self._no_of_evals,
                }
            ),
            headers=self._tenant_header(),
        )

    def _compute_evaluator_scores(self):
        evaluator_scores = []
        evaluator_averages = []

        for evaluator in self._evaluators.values():
            scores = self._evaluator_scores[evaluator.id]
            if scores:
                avg_score = sum(scores) / len(scores)
                evaluator_scores.append(
                    {"value": avg_score, "evaluatorId": evaluator.id}
                )
                evaluator_averages.append(avg_score)
            else:
                # fallback to score 0
                evaluator_scores.append({"value": 0, "evaluatorId": evaluator.id})
                evaluator_averages.append(0)

        overall_score = (
            sum(evaluator_averages) / len(evaluator_averages)
            if evaluator_averages
            else 0
        )
        return evaluator_scores, overall_score

    def _update_eval_set_run_spec(
        self,
    ) -> RequestSpec:
        # this should be removed after computations are done server-side
        evaluator_scores, overall_score = self._compute_evaluator_scores()
        return RequestSpec(
            method="PUT",
            endpoint=Endpoint(
                f"agentsruntime_/api/execution/agents/{self._project_id}/evalSetRun"
            ),
            content=json.dumps(
                {
                    "evalSetRunId": self._eval_set_run_id,
                    "status": EvaluationStatus.COMPLETED.value,
                    "evaluatorScores": evaluator_scores,
                }
            ),
            headers=self._tenant_header(),
        )

    def _tenant_header(self) -> dict[str, str]:
        tenant_id = os.getenv(ENV_TENANT_ID, None)
        if not tenant_id:
            self._console.error(
                f"{ENV_TENANT_ID} env var is not set. Please run 'uipath auth'."
            )
        return {HEADER_INTERNAL_TENANT_ID: tenant_id}  # type: ignore
