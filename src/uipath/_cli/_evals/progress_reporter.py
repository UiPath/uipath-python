"""Progress reporter for sending evaluation updates to StudioWeb."""

import json
import logging
import os
from typing import Any, List

from uipath import UiPath
from uipath._cli._evals._evaluators import EvaluatorBase
from uipath._cli._evals._models import EvaluationResult
from uipath._cli._evals._models._evaluation_set import EvaluationStatus
from uipath._cli._evals._models._evaluators import EvaluatorStatus
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
        self._evaluators = evaluators

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

    async def create_eval_run(self, eval_snapshot: dict[str, Any]):
        """Create a new evaluation run in StudioWeb.

        Args:
            eval_snapshot: Dictionary containing evaluation data

        Returns:
            The ID of the created evaluation run
        """
        spec = self._create_eval_run_spec(eval_snapshot)
        response = await self._client.request_async(
            method=spec.method,
            url=spec.endpoint,
            params=spec.params,
            content=spec.content,
            headers=spec.headers,
            scoped="org",
        )

        return json.loads(response.content)["id"]

    async def update_eval_run(
        self,
        eval_results: dict[str, EvaluationResult],
        eval_run_id: str,
        actual_output: dict[str, Any],
        success: bool,
    ):
        """Update an evaluation run with results.

        Args:
            eval_results: Dictionary mapping evaluator IDs to evaluation results
            eval_run_id: ID of the evaluation run to update
            actual_output: The actual output from the agent
            success: Whether the evaluation was successful
        """
        spec = self._update_eval_run_spec(
            eval_results, eval_run_id, actual_output, success
        )
        await self._client.request_async(
            method=spec.method,
            url=spec.endpoint,
            params=spec.params,
            content=spec.content,
            headers=spec.headers,
            scoped="org",
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
            scoped="org",
        )

        self._eval_set_run_id = json.loads(response.content)["id"]

    async def update_eval_set_run(self):
        """Update the evaluation set run status to completed."""
        spec = self._update_eval_set_run_spec()
        await self._client.request_async(
            method=spec.method,
            url=spec.endpoint,
            params=spec.params,
            content=spec.content,
            headers=spec.headers,
            scoped="org",
        )

    def _update_eval_run_spec(
        self,
        eval_results: dict[str, EvaluationResult],
        eval_run_id: str,
        actual_output: dict[str, Any],
        success: bool,
    ) -> RequestSpec:
        return RequestSpec(
            method="PUT",
            endpoint=Endpoint(
                f"agents_/api/execution/agents/{self._project_id}/evalRun"
            ),
            content=json.dumps(
                {
                    "evalRunId": eval_run_id,
                    "status": EvaluationStatus.COMPLETED.value,
                    "result": {
                        "output": {
                            **actual_output,
                        }
                    },
                    "evaluatorScores": [
                        {
                            # TODO: here we should extract the exact value type (0 = boolean, 1 = numerical, 2 = error)
                            "type": EvaluatorStatus.NUMERICAL.value
                            if success
                            else EvaluatorStatus.ERROR.value,
                            "value": eval_results[evaluator.id].score,  # type: ignore
                            "justification": eval_results[evaluator.id].details,  # type: ignore
                            "evaluatorId": evaluator.id,
                        }
                        for evaluator in self._evaluators
                    ],
                    "completionMetrics": None,
                    "assertionRuns": [],
                }
            ),
            headers=self._tenant_header(),
        )

    def _create_eval_run_spec(self, eval_snapshot: dict[str, Any]) -> RequestSpec:
        return RequestSpec(
            method="POST",
            endpoint=Endpoint(
                f"agents_/api/execution/agents/{self._project_id}/evalRun"
            ),
            content=json.dumps(
                {
                    "evalSetRunId": self._eval_set_run_id,
                    "evalSnapshot": eval_snapshot,
                    "status": EvaluationStatus.IN_PROGRESS.value,
                    "assertionRuns": [
                        {
                            "assertionSnapshot": {
                                "id": evaluator.id,
                                "assertionType": evaluator.type.name,  # type: ignore
                                "targetOutputKey": evaluator.target_output_key,
                            },
                            "status": 1,
                            "evaluatorId": evaluator.id,
                        }
                        for evaluator in self._evaluators
                    ],
                }
            ),
            headers=self._tenant_header(),
        )

    def _create_eval_set_run_spec(
        self,
    ) -> RequestSpec:
        self._add_defaults_to_agent_snapshot()
        # Parse the agent_snapshot JSON string back to a dict for the API call
        agent_snapshot_dict = json.loads(self.agent_snapshot)

        return RequestSpec(
            method="POST",
            endpoint=Endpoint(
                f"agents_/api/execution/agents/{self._project_id}/evalSetRun"
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

    def _update_eval_set_run_spec(
        self,
    ) -> RequestSpec:
        return RequestSpec(
            method="PUT",
            endpoint=Endpoint(
                f"agents_/api/execution/agents/{self._project_id}/evalSetRun"
            ),
            content=json.dumps(
                {
                    ## TODO: send the actual data here (do we need to send those again? isn't it redundant?)
                    "evalSetRunId": self._eval_set_run_id,
                    "score": 0,
                    "status": EvaluationStatus.COMPLETED.value,
                    "evaluatorScores": [],
                }
            ),
            headers=self._tenant_header(),
        )

    def _add_defaults_to_agent_snapshot(self):
        ## TODO: remove this after properties are marked as optional at api level
        agent_snapshot_dict = json.loads(self.agent_snapshot)
        agent_snapshot_dict["tools"] = []
        agent_snapshot_dict["contexts"] = []
        agent_snapshot_dict["escalations"] = []
        agent_snapshot_dict["systemPrompt"] = "unknown"
        agent_snapshot_dict["userPrompt"] = "unknown"
        agent_snapshot_dict["settings"] = {
            "model": "unknown",
            "maxTokens": 0,
            "temperature": 0,
            "engine": "unknown",
        }
        self.agent_snapshot = json.dumps(agent_snapshot_dict)

    def _tenant_header(self) -> dict[str, str]:
        tenant_id = os.getenv(ENV_TENANT_ID, None)
        if not tenant_id:
            self._console.error(
                f"{ENV_TENANT_ID} env var is not set. Please run 'uipath auth'."
            )
        return {HEADER_INTERNAL_TENANT_ID: tenant_id}  # type: ignore
