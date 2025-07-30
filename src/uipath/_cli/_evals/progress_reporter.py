"""Progress reporter for sending evaluation updates to StudioWeb."""

import json
import logging
import os
import uuid
from typing import Any, List, Optional

from uipath import UiPath
from uipath._cli._evals._evaluators import EvaluatorBase
from uipath._cli._evals._models import EvaluationResult
from uipath._cli._evals._models._evaluation_set import EvaluationStatus
from uipath._cli._evals._models._evaluators import EvalItemResult, EvaluatorStatus
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

    async def create_eval_run(self, eval_snapshot: dict[str, Any]) -> Optional[str]:
        """Create a new evaluation run in StudioWeb.

        Args:
            eval_snapshot: Dictionary containing evaluation data

        Returns:
            The ID of the created evaluation run, or None if failed
        """
        try:
            spec = self._create_eval_run_spec(eval_snapshot)
            response = await self._client.request_async(
                method=spec.method,
                url=spec.endpoint,
                params=spec.params,
                content=spec.content,
                headers=spec.headers,
                scoped="tenant",
            )

            result = json.loads(response.content)
            eval_run_id = result.get("id")
            if eval_run_id:
                self._console.info(f"Created EvalRun with ID: {eval_run_id}")
                return eval_run_id
            else:
                self._console.warning("EvalRun creation response missing 'id' field")
                return None

        except Exception as e:
            self._console.warning(f"Failed to create EvalRun for {eval_snapshot.get('name', 'Unknown')}: {str(e)}")
            return None

    async def update_eval_run(
        self,
        eval_results: dict[str, EvaluationResult],
        eval_run_id: str,
        actual_output: dict[str, Any],
        success: bool,
    ) -> None:
        """Update an evaluation run with results.

        Args:
            eval_results: Dictionary mapping evaluator IDs to evaluation results
            eval_run_id: ID of the evaluation run to update
            actual_output: The actual output from the agent
            success: Whether the evaluation was successful
        """
        if not eval_run_id:
            self._console.warning("Cannot update EvalRun: eval_run_id is None")
            return

        try:
            spec = self._update_eval_run_spec(
                eval_results, eval_run_id, actual_output, success
            )
            
            await self._client.request_async(
                method=spec.method,
                url=spec.endpoint,
                params=spec.params,
                content=spec.content,
                headers=spec.headers,
                scoped="tenant",
            )
            self._console.info(f"Successfully updated EvalRun with ID: {eval_run_id}")

        except Exception as e:
            self._console.warning(f"Failed to update EvalRun {eval_run_id}: {str(e)}")

    async def create_eval_set_run(self) -> None:
        """Create a new evaluation set run in StudioWeb."""
        try:
            spec = self._create_eval_set_run_spec()
            response = await self._client.request_async(
                method=spec.method,
                url=spec.endpoint,
                params=spec.params,
                content=spec.content,
                headers=spec.headers,
                scoped="tenant",
            )

            result = json.loads(response.content)
            self._eval_set_run_id = result.get("id")
            
            if self._eval_set_run_id:
                self._console.info(f"Created EvalSetRun with ID: {self._eval_set_run_id}")
            else:
                self._console.warning("EvalSetRun creation response missing 'id' field")

        except Exception as e:
            self._console.warning(f"Failed to create EvalSetRun: {str(e)}")

    async def update_eval_set_run(self, final_results: Optional[dict] = None) -> None:
        """Update the evaluation set run status to completed."""
        try:
            spec = self._update_eval_set_run_spec(final_results)
            
            await self._client.request_async(
                method=spec.method,
                url=spec.endpoint,
                params=spec.params,
                content=spec.content,
                headers=spec.headers,
                scoped="tenant",
            )
            self._console.info(f"Successfully updated EvalSetRun with ID: {self._eval_set_run_id}")

        except Exception as e:
            self._console.warning(f"Failed to update EvalSetRun {self._eval_set_run_id}: {str(e)}")

    def _update_eval_run_spec(
        self,
        eval_results: dict[str, EvaluationResult],
        eval_run_id: str,
        actual_output: dict[str, Any],
        success: bool,
    ) -> RequestSpec:
        # Build evaluator scores and assertion runs
        evaluator_scores = []
        assertion_runs = []
        overall_status = 2  # Default to Success
        
        for i, evaluator in enumerate(self._evaluators):
            if evaluator is not None and evaluator.id in eval_results:
                result = eval_results[evaluator.id]
                
                evaluator_scores.append({
                    "Type": 1,
                    "Value": result.score,
                    "Justification": result.details,
                    "EvaluatorId": result.evaluator_id,
                })
                
                ## TODO: I don't see a way to report if an evaluator failed to run or errored (this would be the "Status" field), Defaulting to success for now
                ## TODO: Generate Completion Metrics for Eval Run (Duration, Tokens, etc). Defaulting to 0 for now. 
                assertion_runs.append({
                    "Status": overall_status,
                    "EvaluatorId": result.evaluator_id,
                    "Result": {
                        "Output": {"reasoning": result.details, "passed": overall_status == 2},
                        "Score": {"Type": 1, "Value": result.score, "Justification": result.details}
                    },
                    # "CompletionMetrics": {"Duration": 0, "Tokens": 0, "CompletionTokens": 0, "PromptTokens": 0}
                })
        
        ## TODO: Generate Completion Metrics for Eval Set Run (Duration, Tokens, etc). Defaulting to 0 for now. 
        return RequestSpec(
            method="PUT",
            endpoint=Endpoint(
                f"agentsruntime_/api/execution/agents/{self._project_id}/evalRun"
            ),
            content=json.dumps(
                {
                    "EvalRunId": eval_run_id,
                    "Status": overall_status,
                    "Result": {
                        "Output": actual_output,
                        "EvaluatorScores": evaluator_scores 
                    },
                    # "CompletionMetrics": {"Duration": 0, "Tokens": 0, "CompletionTokens": 0, "PromptTokens": 0},
                    "AssertionRuns": assertion_runs
                }
            ),
            headers=self._tenant_header(),
        )

    def _create_eval_run_spec(self, eval_snapshot: dict[str, Any]) -> RequestSpec:
        return RequestSpec(
            method="POST",
            endpoint=Endpoint(
                f"agentsruntime_/api/execution/agents/{self._project_id}/evalRun"
            ),
            content=json.dumps(
                {
                    "evalSetRunId": self._eval_set_run_id,
                    ##TODO: AssertionType, AssertionProperties, and OutputKey are legacy fields in Eval Snapshots; they are unused. I will work on removing them from them API call and filling them in on the server-side. 
                    "evalSnapshot": {
                        "id": eval_snapshot["id"],
                        "name": eval_snapshot["name"],
                        "assertionType": "Unknown", 
                        "assertionProperties": {},
                        "inputs": eval_snapshot["inputs"],
                        "outputKey": ""
                    },
                    "status": EvaluationStatus.IN_PROGRESS.value,
                    ##TODO: Will update API to take in assertionRuns list during update call instead of creating it here
                    "assertionRuns": [
                        {
                            "assertionSnapshot": {
                                "assertionType": evaluator.type.name if evaluator.type else "Unknown",
                                "outputKey": evaluator.target_output_key,
                                "assertionProperties": {
                                    "id": evaluator.id,
                                    "name": evaluator.name,
                                    "description": evaluator.description,
                                    "category": evaluator.category.value if evaluator.category else 1,
                                    "type": evaluator.type.value if evaluator.type else 5,
                                    "targetOutputKey": evaluator.target_output_key,
                                }
                            },
                            "status": 1,
                            "evaluatorId": evaluator.id,
                        }
                        for evaluator in self._evaluators
                        if evaluator is not None  # Filter out None evaluators
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

    def _update_eval_set_run_spec(
        self, final_results: Optional[dict] = None
    ) -> RequestSpec:
        # Calculate aggregated scores from final results if available
        average_score = 0.0
        evaluator_scores = []
        
        if final_results and 'results' in final_results:
            average_score = final_results.get('average_score', 0.0)
            results = final_results.get('results', [])
            
            for result in results:
                evaluator_scores.append({
                    "value": result.score,
                    "evaluatorId": result.evaluator_id
                })
        
        return RequestSpec(
            method="PUT",
            endpoint=Endpoint(
                f"agentsruntime_/api/execution/agents/{self._project_id}/evalSetRun"
            ),
            content=json.dumps(
                {
                    ## TODO: send the actual data here (do we need to send those again? isn't it redundant?)
                    "evalSetRunId": self._eval_set_run_id,
                    "score": average_score,
                    "status": EvaluationStatus.COMPLETED.value,
                    "evaluatorScores": evaluator_scores,
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
