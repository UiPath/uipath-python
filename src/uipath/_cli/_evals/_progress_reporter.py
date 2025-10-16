"""Progress reporter for sending evaluation updates to StudioWeb."""

import functools
import json
import logging
import os
from typing import Any, Dict, List

from opentelemetry import trace
from rich.console import Console

from uipath import UiPath
from uipath._cli._evals._models._evaluation_set import (
    AnyEvaluator,
    EvaluationItem,
    EvaluationStatus,
    LegacyEvaluationItem,
)
from uipath._cli._evals._models._sw_reporting import (
    StudioWebAgentSnapshot,
    StudioWebProgressItem,
)
from uipath._cli._utils._console import ConsoleLogger
from uipath._cli._utils._project_files import (  # type: ignore
    get_project_config,
)
from uipath._events._event_bus import EventBus
from uipath._events._events import (
    EvalRunCreatedEvent,
    EvalRunUpdatedEvent,
    EvalSetRunCreatedEvent,
    EvalSetRunUpdatedEvent,
    EvaluationEvents,
)
from uipath._utils import Endpoint, RequestSpec
from uipath._utils.constants import ENV_TENANT_ID, HEADER_INTERNAL_TENANT_ID
from uipath.eval.coded_evaluators import BaseEvaluator
from uipath.eval.evaluators import LegacyBaseEvaluator
from uipath.eval.models import EvalItemResult, ScoreType
from uipath.tracing import LlmOpsHttpExporter

logger = logging.getLogger(__name__)


def gracefully_handle_errors(func):
    """Decorator to catch and log errors without stopping execution."""

    @functools.wraps(func)
    async def wrapper(self, *args, **kwargs):
        try:
            return await func(self, *args, **kwargs)
        except Exception as e:
            if hasattr(self, "_console"):
                error_type = type(e).__name__
                logger.warning(
                    f"Cannot report progress to SW. "
                    f"Function: {func.__name__}, "
                    f"Error type: {error_type}, "
                    f"Details: {e}"
                )
            return None

    return wrapper


class StudioWebProgressReporter:
    """Handles reporting evaluation progress to StudioWeb."""

    def __init__(self, spans_exporter: LlmOpsHttpExporter):
        self.spans_exporter = spans_exporter

        logging.getLogger("uipath._cli.middlewares").setLevel(logging.CRITICAL)
        console_logger = ConsoleLogger.get_instance()
        uipath = UiPath()

        self._client = uipath.api_client
        self._console = console_logger
        self._rich_console = Console()
        self._project_id = os.getenv("UIPATH_PROJECT_ID", None)
        if not self._project_id:
            logger.warning(
                "Cannot report data to StudioWeb. Please set UIPATH_PROJECT_ID."
            )

        self.eval_set_run_ids: Dict[str, str] = {}
        self.evaluators: Dict[str, Any] = {}
        self.evaluator_scores: Dict[str, List[float]] = {}
        self.eval_run_ids: Dict[str, str] = {}
        self.is_coded_eval: Dict[str, bool] = {}  # Track if eval set uses coded evaluators

    def _format_error_message(self, error: Exception, context: str) -> None:
        """Helper method to format and display error messages consistently."""
        self._rich_console.print(f"    • \u26a0  [dim]{context}: {error}[/dim]")

    def _is_coded_evaluator(self, evaluators: List[AnyEvaluator]) -> bool:
        """Detect if evaluators are coded (version 1.0) or legacy.

        Args:
            evaluators: List of evaluators to check

        Returns:
            True if any evaluator is a coded evaluator (BaseEvaluator), False otherwise
        """
        return any(isinstance(e, BaseEvaluator) for e in evaluators)

    @gracefully_handle_errors
    async def create_eval_set_run(
        self,
        eval_set_id: str,
        agent_snapshot: StudioWebAgentSnapshot,
        no_of_evals: int,
        evaluators: List[AnyEvaluator],
        is_coded: bool = False,
    ) -> str:
        """Create a new evaluation set run in StudioWeb."""
        spec = self._create_eval_set_run_spec(
            eval_set_id, agent_snapshot, no_of_evals, is_coded
        )
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
        self,
        eval_item: LegacyEvaluationItem | EvaluationItem,
        eval_set_run_id: str,
        is_coded: bool = False,
    ) -> str:
        """Create a new evaluation run in StudioWeb.

        Args:
            eval_item: Dictionary containing evaluation data
            eval_set_run_id: The ID of the evaluation set run
            is_coded: Whether this is a coded evaluator run

        Returns:
            The ID of the created evaluation run
        """
        spec = self._create_eval_run_spec(eval_item, eval_set_run_id, is_coded)
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
        sw_progress_item: StudioWebProgressItem,
        evaluators: dict[str, AnyEvaluator],
        is_coded: bool = False,
    ):
        """Update an evaluation run with results."""
        if is_coded:
            evaluator_runs, evaluator_scores = self._collect_coded_results(
                sw_progress_item.eval_results, evaluators
            )
            spec = self._update_coded_eval_run_spec(
                evaluator_runs=evaluator_runs,
                evaluator_scores=evaluator_scores,
                eval_run_id=sw_progress_item.eval_run_id,
                execution_time=sw_progress_item.agent_execution_time,
                actual_output=sw_progress_item.agent_output,
            )
        else:
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
        evaluator_scores: dict[str, float],
        is_coded: bool = False,
    ):
        """Update the evaluation set run status to complete."""
        spec = self._update_eval_set_run_spec(
            eval_set_run_id, evaluator_scores, is_coded
        )
        await self._client.request_async(
            method=spec.method,
            url=spec.endpoint,
            params=spec.params,
            json=spec.json,
            headers=spec.headers,
        )

    async def handle_create_eval_set_run(self, payload: EvalSetRunCreatedEvent) -> None:
        try:
            self.evaluators = {eval.id: eval for eval in payload.evaluators}
            self.evaluator_scores = {eval.id: [] for eval in payload.evaluators}

            # Detect if using coded evaluators and store for later use
            is_coded = self._is_coded_evaluator(payload.evaluators)
            self.is_coded_eval[payload.execution_id] = is_coded

            eval_set_run_id = await self.create_eval_set_run(
                eval_set_id=payload.eval_set_id,
                agent_snapshot=self._extract_agent_snapshot(payload.entrypoint),
                no_of_evals=payload.no_of_evals,
                evaluators=payload.evaluators,
                is_coded=is_coded,
            )
            self.eval_set_run_ids[payload.execution_id] = eval_set_run_id
            current_span = trace.get_current_span()
            if current_span.is_recording():
                current_span.set_attribute("eval_set_run_id", eval_set_run_id)

            logger.debug(f"Created eval set run with ID: {eval_set_run_id} (coded={is_coded})")

        except Exception as e:
            self._format_error_message(e, "StudioWeb create eval set run error")

    async def handle_create_eval_run(self, payload: EvalRunCreatedEvent) -> None:
        try:
            if eval_set_run_id := self.eval_set_run_ids.get(payload.execution_id):
                is_coded = self.is_coded_eval.get(payload.execution_id, False)
                eval_run_id = await self.create_eval_run(
                    payload.eval_item, eval_set_run_id, is_coded
                )
                if eval_run_id:
                    self.eval_run_ids[payload.execution_id] = eval_run_id
                    logger.debug(f"Created eval run with ID: {eval_run_id}")
            else:
                logger.warning("Cannot create eval run: eval_set_run_id not available")

        except Exception as e:
            self._format_error_message(e, "StudioWeb create eval run error")

    async def handle_update_eval_run(self, payload: EvalRunUpdatedEvent) -> None:
        try:
            self.spans_exporter.trace_id = self.eval_set_run_ids.get(
                payload.execution_id
            )

            self.spans_exporter.export(payload.spans)

            for eval_result in payload.eval_results:
                evaluator_id = eval_result.evaluator_id
                if evaluator_id in self.evaluator_scores:
                    match eval_result.result.score_type:
                        case ScoreType.NUMERICAL:
                            self.evaluator_scores[evaluator_id].append(
                                eval_result.result.score
                            )
                        case ScoreType.BOOLEAN:
                            self.evaluator_scores[evaluator_id].append(
                                100 if eval_result.result.score else 0
                            )
                        case ScoreType.ERROR:
                            self.evaluator_scores[evaluator_id].append(0)

            eval_run_id = self.eval_run_ids[payload.execution_id]
            if eval_run_id:
                is_coded = self.is_coded_eval.get(payload.execution_id, False)
                await self.update_eval_run(
                    StudioWebProgressItem(
                        eval_run_id=eval_run_id,
                        eval_results=payload.eval_results,
                        success=payload.success,
                        agent_output=payload.agent_output,
                        agent_execution_time=payload.agent_execution_time,
                    ),
                    self.evaluators,
                    is_coded,
                )

                logger.debug(f"Updated eval run with ID: {eval_run_id}")

        except Exception as e:
            self._format_error_message(e, "StudioWeb reporting error")

    async def handle_update_eval_set_run(self, payload: EvalSetRunUpdatedEvent) -> None:
        try:
            if eval_set_run_id := self.eval_set_run_ids.get(payload.execution_id):
                is_coded = self.is_coded_eval.get(payload.execution_id, False)
                await self.update_eval_set_run(
                    eval_set_run_id,
                    payload.evaluator_scores,
                    is_coded,
                )
                logger.debug(f"Updated eval set run with ID: {eval_set_run_id}")
            else:
                logger.warning(
                    "Cannot update eval set run: eval_set_run_id not available"
                )

        except Exception as e:
            self._format_error_message(e, "StudioWeb update eval set run error")

    async def subscribe_to_eval_runtime_events(self, event_bus: EventBus) -> None:
        event_bus.subscribe(
            EvaluationEvents.CREATE_EVAL_SET_RUN, self.handle_create_eval_set_run
        )
        event_bus.subscribe(
            EvaluationEvents.CREATE_EVAL_RUN, self.handle_create_eval_run
        )
        event_bus.subscribe(
            EvaluationEvents.UPDATE_EVAL_RUN, self.handle_update_eval_run
        )
        event_bus.subscribe(
            EvaluationEvents.UPDATE_EVAL_SET_RUN, self.handle_update_eval_set_run
        )

        logger.debug("StudioWeb progress reporter subscribed to evaluation events")

    def _extract_agent_snapshot(self, entrypoint: str) -> StudioWebAgentSnapshot:
        try:
            project_config = get_project_config(os.getcwd())
            ep = None
            for entry_point in project_config.get("entryPoints", []):
                if entry_point.get("filePath") == entrypoint:
                    ep = entry_point
                    break

            if not ep:
                logger.warning(
                    f"Entrypoint {entrypoint} not found in configuration file"
                )
                return StudioWebAgentSnapshot(input_schema={}, output_schema={})

            input_schema = ep.get("input", {})
            output_schema = ep.get("output", {})

            return StudioWebAgentSnapshot(
                input_schema=input_schema, output_schema=output_schema
            )
        except Exception as e:
            logger.warning(f"Failed to extract agent snapshot: {e}")
            return StudioWebAgentSnapshot(input_schema={}, output_schema={})

    def _collect_results(
        self,
        eval_results: list[EvalItemResult],
        evaluators: dict[str, LegacyBaseEvaluator[Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Collect results for legacy evaluators (assertionRuns)."""
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

    def _collect_coded_results(
        self,
        eval_results: list[EvalItemResult],
        evaluators: dict[str, AnyEvaluator],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Collect results for coded evaluators (evaluatorRuns)."""
        evaluator_runs: list[dict[str, Any]] = []
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
            evaluator = evaluators.get(eval_result.evaluator_id)
            evaluator_runs.append(
                {
                    "evaluatorId": eval_result.evaluator_id,
                    "status": EvaluationStatus.COMPLETED.value,
                    "evaluatorSnapshot": None,  # TODO: Add evaluator snapshot
                    "evaluationCriteria": None,  # TODO: Add evaluation criteria if needed
                    "result": {
                        "output": {},
                        "score": {
                            "type": eval_result.result.score_type.value,
                            "value": eval_result.result.score,
                            "justification": eval_result.result.details,
                        },
                    },
                    "completionMetrics": {
                        "duration": int(eval_result.result.evaluation_time)
                        if eval_result.result.evaluation_time
                        else 0,
                        "cost": None,
                        "tokens": 0,
                        "completionTokens": 0,
                        "promptTokens": 0,
                    },
                }
            )
        return evaluator_runs, evaluator_scores_list

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

    def _update_coded_eval_run_spec(
        self,
        evaluator_runs: list[dict[str, Any]],
        evaluator_scores: list[dict[str, Any]],
        eval_run_id: str,
        actual_output: dict[str, Any],
        execution_time: float,
    ) -> RequestSpec:
        """Update spec for coded evaluator runs (version 1.0 schema)."""
        return RequestSpec(
            method="PUT",
            endpoint=Endpoint(
                f"agentsruntime_/api/execution/agents/{self._project_id}/coded/evalRun"
            ),
            json={
                "evalRunId": eval_run_id,
                "status": EvaluationStatus.COMPLETED.value,
                "result": {
                    "output": {**actual_output},
                    "scores": evaluator_scores,
                },
                "completionMetrics": {"duration": int(execution_time)},
                "evaluatorRuns": evaluator_runs,
            },
            headers=self._tenant_header(),
        )

    def _create_eval_run_spec(
        self, eval_item: LegacyEvaluationItem | EvaluationItem, eval_set_run_id: str, is_coded: bool = False
    ) -> RequestSpec:
        # Route to /coded/ endpoints for coded evaluators
        endpoint_path = "coded/evalRun" if is_coded else "evalRun"

        # For coded evaluators, use evaluationCriterias; for legacy, use expectedOutput
        if is_coded and isinstance(eval_item, EvaluationItem):
            eval_snapshot = {
                "id": eval_item.id,
                "name": eval_item.name,
                "inputs": eval_item.inputs,
                "evaluationCriterias": eval_item.evaluation_criterias,
            }
        else:
            eval_snapshot = {
                "id": eval_item.id,
                "name": eval_item.name,
                "inputs": eval_item.inputs,
                "expectedOutput": eval_item.expected_output,
            }

        return RequestSpec(
            method="POST",
            endpoint=Endpoint(
                f"agentsruntime_/api/execution/agents/{self._project_id}/{endpoint_path}"
            ),
            json={
                "evalSetRunId": eval_set_run_id,
                "evalSnapshot": eval_snapshot,
                "status": EvaluationStatus.IN_PROGRESS.value,
            },
            headers=self._tenant_header(),
        )

    def _create_eval_set_run_spec(
        self,
        eval_set_id: str,
        agent_snapshot: StudioWebAgentSnapshot,
        no_of_evals: int,
        is_coded: bool = False,
    ) -> RequestSpec:
        # Route to /coded/ endpoints for coded evaluators
        endpoint_path = "coded/evalSetRun" if is_coded else "evalSetRun"

        payload = {
            "agentId": self._project_id,
            "evalSetId": eval_set_id,
            "agentSnapshot": agent_snapshot.model_dump(by_alias=True),
            "status": EvaluationStatus.IN_PROGRESS.value,
            "numberOfEvalsExecuted": no_of_evals,
        }

        # Add version for coded evaluators
        if is_coded:
            payload["version"] = "1.0"

        return RequestSpec(
            method="POST",
            endpoint=Endpoint(
                f"agentsruntime_/api/execution/agents/{self._project_id}/{endpoint_path}"
            ),
            json=payload,
            headers=self._tenant_header(),
        )

    def _update_eval_set_run_spec(
        self,
        eval_set_run_id: str,
        evaluator_scores: dict[str, float],
        is_coded: bool = False,
    ) -> RequestSpec:
        evaluator_scores_list = [
            {"value": avg_score, "evaluatorId": evaluator_id}
            for evaluator_id, avg_score in evaluator_scores.items()
        ]

        # Route to /coded/ endpoints for coded evaluators
        endpoint_path = "coded/evalSetRun" if is_coded else "evalSetRun"

        return RequestSpec(
            method="PUT",
            endpoint=Endpoint(
                f"agentsruntime_/api/execution/agents/{self._project_id}/{endpoint_path}"
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
