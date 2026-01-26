"""Progress reporter for sending evaluation updates to StudioWeb."""

import functools
import json
import logging
import os
import uuid
from typing import Any
from urllib.parse import urlparse

from opentelemetry import trace
from pydantic import BaseModel
from rich.console import Console

from uipath._cli._evals._models._evaluation_set import (
    EvaluationItem,
    EvaluationStatus,
)
from uipath._cli._evals._models._evaluator import Evaluator
from uipath._cli._evals._models._sw_reporting import (
    StudioWebAgentSnapshot,
    StudioWebProgressItem,
)
from uipath._cli._utils._console import ConsoleLogger
from uipath._events._event_bus import EventBus
from uipath._events._events import (
    EvalRunCreatedEvent,
    EvalRunUpdatedEvent,
    EvalSetRunCreatedEvent,
    EvalSetRunUpdatedEvent,
    EvaluationEvents,
)
from uipath._utils import Endpoint, RequestSpec
from uipath._utils.constants import (
    ENV_EVAL_BACKEND_URL,
    ENV_TENANT_ID,
    HEADER_INTERNAL_TENANT_ID,
)
from uipath.eval.evaluators import (
    BaseEvaluator,
    LegacyBaseEvaluator,
)
from uipath.eval.models import EvalItemResult, ScoreType
from uipath.platform import UiPath
from uipath.platform.common import UiPathConfig
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
                # Log the full error message for debugging
                logger.debug(f"Full error details: {e}")
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

        # Use UIPATH_EVAL_BACKEND_URL for eval-specific routing if set
        eval_backend_url = os.getenv(ENV_EVAL_BACKEND_URL)
        uipath = UiPath(base_url=eval_backend_url) if eval_backend_url else UiPath()

        self._client = uipath.api_client
        self._console = console_logger
        self._rich_console = Console()
        self._project_id = os.getenv("UIPATH_PROJECT_ID", None)
        if not self._project_id:
            logger.warning(
                "Cannot report data to StudioWeb. Please set UIPATH_PROJECT_ID."
            )

        self.eval_set_ids: dict[str, str] = {}  # Track eval_set_id per execution
        self.eval_set_run_ids: dict[str, str] = {}
        self.evaluators: dict[str, Any] = {}
        self.evaluator_scores: dict[str, list[float]] = {}
        self.eval_run_ids: dict[str, str] = {}
        self.is_coded_eval: dict[str, bool] = {}  # Track coded vs legacy per execution
        self.is_resume_mode: dict[str, bool] = {}  # Track resume mode per execution
        self.eval_spans: dict[
            str, list[Any]
        ] = {}  # Store spans per execution for usage metrics
        self.eval_set_execution_id: str | None = (
            None  # Track current eval set execution ID
        )
        self.user_provided_eval_set_run_ids: set[str] = (
            set()
        )  # Track user-provided eval_set_run_ids

    @gracefully_handle_errors
    async def get_eval_run_for_evaluation(
        self,
        eval_set_id: str,
        eval_set_run_id: str,
        evaluation_id: str,
        is_coded: bool = False,
    ) -> str | None:
        """Get the eval_run_id for a specific evaluation from the backend.

        This is used during resume to fetch the eval_run_id for the specific
        evaluation being executed, using the backend database as the source of truth.

        Args:
            eval_set_id: The eval set ID
            eval_set_run_id: The eval set run ID
            evaluation_id: The specific evaluation ID being executed
            is_coded: Whether this is a coded evaluation (vs legacy)

        Returns:
            The eval_run_id if found, None otherwise
        """
        logger.info(
            f"Fetching eval runs from backend: eval_set_id={eval_set_id}, "
            f"eval_set_run_id={eval_set_run_id}, evaluation_id={evaluation_id}, coded={is_coded}"
        )

        spec = self._get_eval_runs_spec(
            eval_set_id, eval_set_run_id, evaluation_id, is_coded
        )

        logger.debug(f"GET request endpoint: {spec.endpoint}")

        response = await self._client.request_async(
            method=spec.method,
            url=spec.endpoint,
            params=spec.params,
            headers=spec.headers,
            scoped="org" if self._is_localhost() else "tenant",
        )

        logger.info(
            f"GET eval runs response: status_code={response.status_code}, "
            f"content_length={len(response.content)} bytes"
        )

        # Parse response to find the eval run matching this evaluation_id
        response_data = json.loads(response.content)
        logger.debug(
            f"GET eval run response data for evaluation_id={evaluation_id}: {json.dumps(response_data, indent=2)}"
        )

        # Extract eval runs from response
        # Response format may vary between coded and legacy APIs
        eval_runs = (
            response_data
            if isinstance(response_data, list)
            else response_data.get("value", [])
        )

        logger.info(
            f"Backend returned {len(eval_runs)} eval run(s) for eval_set_run_id={eval_set_run_id}"
        )

        # Find the eval run that matches our evaluation_id
        for idx, eval_run in enumerate(eval_runs):
            eval_snapshot = eval_run.get("evalSnapshot", {})
            snapshot_eval_id = str(eval_snapshot.get("id", ""))
            eval_run_id_in_response = eval_run.get("id")

            logger.debug(
                f"Checking eval run [{idx}]: eval_run_id={eval_run_id_in_response}, "
                f"snapshot_eval_id={snapshot_eval_id}, target_evaluation_id={evaluation_id}"
            )

            if snapshot_eval_id == evaluation_id:
                eval_run_id = eval_run.get("id")
                if eval_run_id:
                    logger.info(
                        f"✓ MATCH FOUND: eval_run_id={eval_run_id} matches evaluation_id={evaluation_id} (resume scenario)"
                    )
                    return eval_run_id
                else:
                    logger.warning(
                        f"Found matching eval snapshot with evaluation_id={evaluation_id} but eval_run_id is missing in response"
                    )

        logger.warning(
            f"✗ NO MATCH: No eval run found in backend for evaluation_id={evaluation_id}. "
            f"Searched {len(eval_runs)} eval run(s) in eval_set_run_id={eval_set_run_id}. "
            f"Available evaluation IDs: {[str(er.get('evalSnapshot', {}).get('id', '')) for er in eval_runs]}"
        )
        return None

    async def fetch_and_cache_eval_runs(
        self,
        eval_set_id: str,
        eval_set_run_id: str,
        is_coded: bool = False,
    ) -> None:
        """Fetch all eval runs from backend and populate cache.

        This is used during resume to pre-populate the eval_run_id cache with
        all existing eval runs from the backend database.

        Args:
            eval_set_id: The eval set ID
            eval_set_run_id: The eval set run ID
            is_coded: Whether this is a coded evaluation (vs legacy)
        """
        logger.info(
            f"🔄 RESUME FLOW: Fetching all eval runs from backend to populate cache: "
            f"eval_set_id={eval_set_id}, eval_set_run_id={eval_set_run_id}, coded={is_coded}"
        )

        # Use empty evaluation_id to fetch all eval runs (not filtering by specific evaluation)
        spec = self._get_eval_runs_spec(
            eval_set_id, eval_set_run_id, evaluation_id="", is_coded=is_coded
        )

        logger.debug(f"GET all eval runs endpoint: {spec.endpoint}")

        response = await self._client.request_async(
            method=spec.method,
            url=spec.endpoint,
            params=spec.params,
            headers=spec.headers,
            scoped="org" if self._is_localhost() else "tenant",
        )

        logger.info(
            f"GET all eval runs response: status_code={response.status_code}, "
            f"content_length={len(response.content)} bytes"
        )

        # Parse response to extract all eval runs
        response_data = json.loads(response.content)

        # Extract eval runs from response
        # Response format may vary between coded and legacy APIs
        eval_runs = (
            response_data
            if isinstance(response_data, list)
            else response_data.get("value", [])
        )

        logger.info(
            f"✓ Backend returned {len(eval_runs)} eval run(s) for eval_set_run_id={eval_set_run_id}"
        )

        # Populate cache with all eval runs
        cached_count = 0
        for eval_run in eval_runs:
            eval_snapshot = eval_run.get("evalSnapshot", {})
            evaluation_id = str(eval_snapshot.get("id", ""))
            eval_run_id = eval_run.get("id")

            if evaluation_id and eval_run_id:
                # Cache using evaluation_id as the key
                # Since we don't have execution_id yet, we'll need to map by evaluation_id
                # Store in a temporary mapping that will be used when CREATE_EVAL_RUN would have fired
                self.eval_run_ids[evaluation_id] = eval_run_id
                cached_count += 1
                logger.debug(
                    f"✓ Cached eval_run_id={eval_run_id} for evaluation_id={evaluation_id}"
                )

        logger.info(
            f"✓ RESUME FLOW: Successfully cached {cached_count}/{len(eval_runs)} eval runs"
        )

    def _format_error_message(self, error: Exception, context: str) -> None:
        """Helper method to format and display error messages consistently."""
        self._rich_console.print(f"    • \u26a0  [dim]{context}: {error}[/dim]")

    def _is_localhost(self) -> bool:
        """Check if the eval backend URL is localhost.

        Returns:
            True if using localhost, False otherwise.
        """
        eval_backend_url = os.getenv(ENV_EVAL_BACKEND_URL, "")
        if eval_backend_url:
            try:
                parsed = urlparse(eval_backend_url)
                hostname = parsed.hostname or parsed.netloc.split(":")[0]
                return hostname.lower() in ("localhost", "127.0.0.1")
            except Exception:
                pass
        return False

    def _get_endpoint_prefix(self) -> str:
        """Determine the endpoint prefix based on environment.

        Checks UIPATH_EVAL_BACKEND_URL environment variable:
        - If set to localhost/127.0.0.1: returns "api/" (direct API access)
        - Otherwise: returns "agentsruntime_/api/" (service routing for alpha/prod)

        Returns:
            "api/" for localhost environments, "agentsruntime_/api/" for alpha/production.
        """
        if self._is_localhost():
            return "api/"
        return "agentsruntime_/api/"

    def _is_coded_evaluator(
        self, evaluators: list[BaseEvaluator[Any, Any, Any]]
    ) -> bool:
        """Check if evaluators are coded (BaseEvaluator) vs legacy (LegacyBaseEvaluator).

        Args:
            evaluators: List of evaluators to check

        Returns:
            True if using coded evaluators, False for legacy evaluators
        """
        if not evaluators:
            return False
        # Check the first evaluator type
        return not isinstance(evaluators[0], LegacyBaseEvaluator)

    def _extract_usage_from_spans(
        self, spans: list[Any]
    ) -> dict[str, int | float | None]:
        """Extract token usage and cost from OpenTelemetry spans.

        Args:
            spans: List of ReadableSpan objects from agent execution

        Returns:
            Dictionary with tokens, completionTokens, promptTokens, and cost
        """
        total_tokens = 0
        completion_tokens = 0
        prompt_tokens = 0
        total_cost = 0.0

        for span in spans:
            try:
                # Handle both dictionary attributes and string Attributes field
                attrs = None
                if hasattr(span, "attributes") and span.attributes:
                    if isinstance(span.attributes, dict):
                        attrs = span.attributes
                    elif isinstance(span.attributes, str):
                        # Parse JSON string attributes
                        attrs = json.loads(span.attributes)

                # Also check for Attributes field (capitalized) from backend spans
                if not attrs and hasattr(span, "Attributes") and span.Attributes:
                    if isinstance(span.Attributes, str):
                        attrs = json.loads(span.Attributes)
                    elif isinstance(span.Attributes, dict):
                        attrs = span.Attributes

                if attrs:
                    # Try to get usage from nested usage object (backend format)
                    if "usage" in attrs and isinstance(attrs["usage"], dict):
                        usage = attrs["usage"]
                        prompt_tokens += usage.get("promptTokens", 0)
                        completion_tokens += usage.get("completionTokens", 0)
                        total_tokens += usage.get("totalTokens", 0)
                        # Cost might be in usage or at root level
                        total_cost += usage.get("cost", 0.0)

                    # Also try OpenTelemetry semantic conventions (SDK format)
                    prompt_tokens += attrs.get("gen_ai.usage.prompt_tokens", 0)
                    completion_tokens += attrs.get("gen_ai.usage.completion_tokens", 0)
                    total_tokens += attrs.get("gen_ai.usage.total_tokens", 0)
                    total_cost += attrs.get("gen_ai.usage.cost", 0.0)
                    total_cost += attrs.get("llm.usage.cost", 0.0)

            except (json.JSONDecodeError, AttributeError, TypeError) as e:
                logger.debug(f"Failed to parse span attributes: {e}")
                continue

        return {
            "tokens": total_tokens if total_tokens > 0 else None,
            "completionTokens": completion_tokens if completion_tokens > 0 else None,
            "promptTokens": prompt_tokens if prompt_tokens > 0 else None,
            "cost": total_cost if total_cost > 0 else None,
        }

    @gracefully_handle_errors
    async def create_eval_set_run_sw(
        self,
        eval_set_id: str,
        agent_snapshot: StudioWebAgentSnapshot,
        no_of_evals: int,
        evaluators: list[LegacyBaseEvaluator[Any]],
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
            scoped="org" if self._is_localhost() else "tenant",
        )
        eval_set_run_id = json.loads(response.content)["id"]
        return eval_set_run_id

    @gracefully_handle_errors
    async def create_eval_run(
        self, eval_item: EvaluationItem, eval_set_run_id: str, is_coded: bool = False
    ) -> str | None:
        """Create a new evaluation run in StudioWeb.

        Args:
            eval_item: Dictionary containing evaluation data
            eval_set_run_id: The ID of the evaluation set run
            is_coded: Whether this is a coded evaluation (vs legacy)

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
            scoped="org" if self._is_localhost() else "tenant",
        )

        # Parse response and extract eval_run_id
        response_data = json.loads(response.content)
        logger.debug(f"CREATE_EVAL_RUN response: {response_data}")

        eval_run_id = response_data.get("id")
        if not eval_run_id:
            logger.error(f"No 'id' field in CREATE_EVAL_RUN response: {response_data}")
            return None

        return eval_run_id

    @gracefully_handle_errors
    async def update_eval_run(
        self,
        sw_progress_item: StudioWebProgressItem,
        evaluators: dict[str, Evaluator],
        is_coded: bool = False,
        spans: list[Any] | None = None,
    ):
        """Update an evaluation run with results."""
        coded_evaluators: dict[str, BaseEvaluator[Any, Any, Any]] = {}
        legacy_evaluators: dict[str, LegacyBaseEvaluator[Any]] = {}
        evaluator_runs: list[dict[str, Any]] = []
        evaluator_scores: list[dict[str, Any]] = []

        for k, v in evaluators.items():
            if isinstance(v, LegacyBaseEvaluator):
                legacy_evaluators[k] = v
            elif isinstance(v, BaseEvaluator):
                coded_evaluators[k] = v

        # Use coded evaluator format
        runs, scores = self._collect_coded_results(
            sw_progress_item.eval_results, coded_evaluators, spans or []
        )
        evaluator_runs.extend(runs)
        evaluator_scores.extend(scores)

        # Use legacy evaluator format
        runs, scores = self._collect_results(
            sw_progress_item.eval_results,
            legacy_evaluators,
            spans or [],
        )
        evaluator_runs.extend(runs)
        evaluator_scores.extend(scores)

        # Use the appropriate spec method based on evaluation type
        if is_coded:
            spec = self._update_coded_eval_run_spec(
                evaluator_runs=evaluator_runs,
                evaluator_scores=evaluator_scores,
                eval_run_id=sw_progress_item.eval_run_id,
                execution_time=sw_progress_item.agent_execution_time,
                actual_output=sw_progress_item.agent_output,
                success=sw_progress_item.success,
                is_coded=is_coded,
            )
        else:
            spec = self._update_eval_run_spec(
                assertion_runs=evaluator_runs,
                evaluator_scores=evaluator_scores,
                eval_run_id=sw_progress_item.eval_run_id,
                execution_time=sw_progress_item.agent_execution_time,
                actual_output=sw_progress_item.agent_output,
                success=sw_progress_item.success,
                is_coded=is_coded,
            )

        await self._client.request_async(
            method=spec.method,
            url=spec.endpoint,
            params=spec.params,
            json=spec.json,
            headers=spec.headers,
            scoped="org" if self._is_localhost() else "tenant",
        )

    @gracefully_handle_errors
    async def update_eval_set_run(
        self,
        eval_set_run_id: str,
        evaluator_scores: dict[str, float],
        is_coded: bool = False,
        success: bool = True,
    ):
        """Update the evaluation set run status to complete."""
        spec = self._update_eval_set_run_spec(
            eval_set_run_id, evaluator_scores, is_coded, success
        )
        await self._client.request_async(
            method=spec.method,
            url=spec.endpoint,
            params=spec.params,
            json=spec.json,
            headers=spec.headers,
            scoped="org" if self._is_localhost() else "tenant",
        )

    async def handle_create_eval_set_run(self, payload: EvalSetRunCreatedEvent) -> None:
        try:
            self.evaluators = {eval.id: eval for eval in payload.evaluators}
            self.evaluator_scores = {eval.id: [] for eval in payload.evaluators}

            # Store the eval set execution ID for mapping eval runs to eval set
            self.eval_set_execution_id = payload.execution_id

            # Store the eval_set_id for this execution (needed for backend API calls)
            self.eval_set_ids[payload.execution_id] = payload.eval_set_id

            # Detect if using coded evaluators and store for this execution
            is_coded = self._is_coded_evaluator(payload.evaluators)
            self.is_coded_eval[payload.execution_id] = is_coded

            # Check if eval_set_run_id is provided (resume scenario)
            eval_set_run_id = payload.eval_set_run_id
            if eval_set_run_id:
                self.user_provided_eval_set_run_ids.add(eval_set_run_id)
                # Resume scenario: Use the provided eval_set_run_id
                # Fetch all existing eval runs from backend to populate cache
                self.is_resume_mode[payload.execution_id] = True
                logger.info(
                    f"Resume scenario: Using provided eval_set_run_id={eval_set_run_id}"
                )

                # Fetch all eval runs for this eval_set_run_id to populate cache
                # Gracefully handle errors so we don't block the resume flow
                try:
                    await self.fetch_and_cache_eval_runs(
                        eval_set_id=payload.eval_set_id,
                        eval_set_run_id=eval_set_run_id,
                        is_coded=is_coded,
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to fetch eval runs from backend during resume: {e}. "
                        "Will continue with empty cache."
                    )
            else:
                # Normal scenario: Create a new eval set run in the backend
                self.is_resume_mode[payload.execution_id] = False
                eval_set_run_id = await self.create_eval_set_run_sw(
                    eval_set_id=payload.eval_set_id,
                    agent_snapshot=self._extract_agent_snapshot(payload.entrypoint),
                    no_of_evals=payload.no_of_evals,
                    evaluators=payload.evaluators,
                    is_coded=is_coded,
                )
                logger.info(f"Created new eval_set_run_id: {eval_set_run_id}")

            self.eval_set_run_ids[payload.execution_id] = eval_set_run_id

            current_span = trace.get_current_span()
            if current_span.is_recording():
                current_span.set_attribute("eval_set_run_id", eval_set_run_id)

            # Do NOT set global trace_id override here
            # Trace IDs are set per-evaluation in handle_update_eval_run()

            logger.debug(
                f"Created eval set run with ID: {eval_set_run_id} (coded={is_coded})"
            )

        except Exception as e:
            self._format_error_message(e, "StudioWeb create eval set run error")

    async def handle_create_eval_run(self, payload: EvalRunCreatedEvent) -> None:
        try:
            logger.info(
                f"Processing CREATE_EVAL_RUN event: execution_id={payload.execution_id}, "
                f"evaluation_id={payload.eval_item.id}"
            )

            # Check if we already have an eval_run_id cached
            existing_eval_run_id = self.eval_run_ids.get(payload.execution_id)

            if existing_eval_run_id:
                # Already have eval_run_id (from previous fetch or creation)
                logger.info(
                    f"Using cached eval_run_id={existing_eval_run_id} for execution_id={payload.execution_id} "
                    f"(skipping backend fetch/create)"
                )
                return

            # Get eval_set_id, eval_set_run_id and is_coded flag
            if not self.eval_set_execution_id:
                logger.warning("Cannot process eval run: eval_set_execution_id not set")
                return

            eval_set_id = self.eval_set_ids.get(self.eval_set_execution_id)
            if not eval_set_id:
                logger.warning(
                    f"Cannot process eval run: eval_set_id not available for eval_set_execution_id={self.eval_set_execution_id}"
                )
                return

            eval_set_run_id = self.eval_set_run_ids.get(self.eval_set_execution_id)
            if not eval_set_run_id:
                logger.warning(
                    f"Cannot process eval run: eval_set_run_id not available for eval_set_execution_id={self.eval_set_execution_id}"
                )
                return

            is_coded = self.is_coded_eval.get(self.eval_set_execution_id, False)

            # Check if we're in resume mode (eval_set_run_id was provided vs created)
            is_resume = self.is_resume_mode.get(self.eval_set_execution_id, False)

            logger.info(
                f"Retrieved context: eval_set_id={eval_set_id}, eval_set_run_id={eval_set_run_id}, "
                f"is_coded={is_coded}, is_resume={is_resume}, eval_set_execution_id={self.eval_set_execution_id}"
            )

            evaluation_id = payload.eval_item.id
            eval_run_id = None

            # Only fetch from backend if we're in resume mode
            # In normal mode, we know eval runs don't exist yet (we just created eval_set_run)
            if is_resume:
                logger.info(
                    f"Resume mode: Attempting to fetch existing eval_run_id from backend for evaluation_id={evaluation_id}"
                )

                # Try to fetch existing eval run from backend (resume scenario)
                eval_run_id = await self.get_eval_run_for_evaluation(
                    eval_set_id, eval_set_run_id, evaluation_id, is_coded
                )

                if eval_run_id:
                    # Resume scenario: Found existing eval run in backend
                    self.eval_run_ids[payload.execution_id] = eval_run_id
                    logger.info(
                        f"✓ RESUME FLOW: Successfully cached eval_run_id={eval_run_id} for "
                        f"execution_id={payload.execution_id}, evaluation_id={evaluation_id}. "
                        f"Loaded from backend database."
                    )
                else:
                    logger.warning(
                        f"Resume mode but no eval_run_id found in backend for evaluation_id={evaluation_id}. "
                        f"Will create new eval run."
                    )

            # Create new eval run if not in resume mode OR if backend fetch didn't find one
            if not eval_run_id:
                logger.info(
                    f"{'Normal mode' if not is_resume else 'Resume mode (no existing run found)'}: "
                    f"Creating new eval run for evaluation_id={evaluation_id}, eval_set_run_id={eval_set_run_id}"
                )

                eval_run_id = await self.create_eval_run(
                    payload.eval_item, eval_set_run_id, is_coded
                )
                if eval_run_id:
                    # Store eval_run_id with the individual eval run's execution_id
                    self.eval_run_ids[payload.execution_id] = eval_run_id

                    logger.info(
                        f"✓ NORMAL FLOW: Successfully created and cached eval_run_id={eval_run_id} for "
                        f"execution_id={payload.execution_id}, evaluation_id={evaluation_id}, "
                        f"eval_set_run_id={eval_set_run_id} (coded={is_coded})"
                    )
                else:
                    logger.error(
                        f"✗ ERROR: create_eval_run returned None for execution_id={payload.execution_id}, "
                        f"evaluation_id={evaluation_id}, eval_set_run_id={eval_set_run_id}, is_coded={is_coded}"
                    )

        except Exception as e:
            self._format_error_message(e, "StudioWeb create eval run error")

    async def handle_update_eval_run(self, payload: EvalRunUpdatedEvent) -> None:
        try:
            logger.info(
                f"Processing UPDATE_EVAL_RUN event: execution_id={payload.execution_id}, "
                f"success={payload.success}"
            )

            eval_run_id = self.eval_run_ids.get(payload.execution_id)

            if not eval_run_id:
                logger.warning(
                    f"Cannot update eval run: eval_run_id not found in cache for "
                    f"execution_id={payload.execution_id}. Available keys: {list(self.eval_run_ids.keys())}"
                )
            else:
                logger.info(
                    f"Found eval_run_id={eval_run_id} for execution_id={payload.execution_id} in cache"
                )

            # Export spans using the eval_set_run_id as trace_id (already set during CREATE_EVAL_SET_RUN)
            # Individual eval runs are distinguished by span attributes, not separate trace IDs
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

            if eval_run_id and self.eval_set_execution_id:
                # Get the is_coded flag for this execution
                is_coded = self.is_coded_eval.get(self.eval_set_execution_id, False)

                logger.info(
                    f"Sending UPDATE to backend: eval_run_id={eval_run_id}, "
                    f"is_coded={is_coded}, success={payload.success}"
                )

                # Extract usage metrics from spans
                self._extract_usage_from_spans(payload.spans)

                await self.update_eval_run(
                    StudioWebProgressItem(
                        eval_run_id=eval_run_id,
                        eval_results=payload.eval_results,
                        success=payload.success,
                        agent_output=payload.agent_output,
                        agent_execution_time=payload.agent_execution_time,
                    ),
                    self.evaluators,
                    is_coded=is_coded,
                    spans=payload.spans,
                )

                logger.info(
                    f"✓ Successfully updated eval_run_id={eval_run_id} in backend (coded={is_coded})"
                )

        except Exception as e:
            self._format_error_message(e, "StudioWeb reporting error")

    async def handle_update_eval_set_run(self, payload: EvalSetRunUpdatedEvent) -> None:
        try:
            if eval_set_run_id := self.eval_set_run_ids.get(payload.execution_id):
                # Skip update if eval_set_run_id was provided by user
                if eval_set_run_id in self.user_provided_eval_set_run_ids:
                    logger.debug(
                        f"Skipping eval set run update for user-provided eval_set_run_id (eval_set_run_id={eval_set_run_id})"
                    )
                    return
                # Get the is_coded flag for this execution
                is_coded = self.is_coded_eval.get(payload.execution_id, False)
                await self.update_eval_set_run(
                    eval_set_run_id,
                    payload.evaluator_scores,
                    is_coded=is_coded,
                    success=payload.success,
                )
                status_str = "completed" if payload.success else "failed"
                logger.debug(
                    f"Updated eval set run with ID: {eval_set_run_id} (coded={is_coded}, status={status_str})"
                )
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

    def _serialize_justification(
        self, justification: BaseModel | str | None
    ) -> str | None:
        """Serialize justification to JSON string for API compatibility.

        Args:
            justification: The justification object which could be None, a BaseModel,
                          a string, or any other JSON-serializable object

        Returns:
            JSON string representation or None if justification is None
        """
        if isinstance(justification, BaseModel):
            justification = json.dumps(justification.model_dump())

        return justification

    def _extract_agent_snapshot(self, entrypoint: str | None) -> StudioWebAgentSnapshot:
        """Extract agent snapshot from entry points configuration or low-code agent file.

        For coded agents, reads from entry-points.json configuration file.
        For low-code agents (*.json files like agent.json), reads inputSchema
        and outputSchema directly from the agent file.

        Args:
            entrypoint: The entrypoint file path to look up

        Returns:
            StudioWebAgentSnapshot with input and output schemas
        """
        if not entrypoint:
            logger.warning(
                "Entrypoint not provided - falling back to empty inputSchema "
                "and outputSchema"
            )
            return StudioWebAgentSnapshot(input_schema={}, output_schema={})

        try:
            # Check if entrypoint is a low-code agent JSON file (e.g., agent.json)
            if entrypoint.endswith(".json"):
                agent_file_path = os.path.join(os.getcwd(), entrypoint)
                if os.path.exists(agent_file_path):
                    with open(agent_file_path, "r") as f:
                        agent_data = json.load(f)

                    # Low-code agent files have inputSchema and outputSchema at root
                    input_schema = agent_data.get("inputSchema", {})
                    output_schema = agent_data.get("outputSchema", {})

                    logger.debug(
                        f"Extracted agent snapshot from low-code agent '{entrypoint}': "
                        f"inputSchema={json.dumps(input_schema)}, "
                        f"outputSchema={json.dumps(output_schema)}"
                    )

                    return StudioWebAgentSnapshot(
                        input_schema=input_schema, output_schema=output_schema
                    )

            # Fall back to entry-points.json for coded agents
            entry_points_file_path = os.path.join(
                os.getcwd(), str(UiPathConfig.entry_points_file_path)
            )
            if not os.path.exists(entry_points_file_path):
                logger.debug(
                    f"Entry points file not found at {entry_points_file_path}, "
                    "using empty schemas"
                )
                return StudioWebAgentSnapshot(input_schema={}, output_schema={})

            with open(entry_points_file_path, "r") as f:
                entry_points = json.load(f).get("entryPoints", [])

            ep = None
            for entry_point in entry_points:
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

            logger.debug(
                f"Extracted agent snapshot for entrypoint '{entrypoint}': "
                f"inputSchema={json.dumps(input_schema)}, "
                f"outputSchema={json.dumps(output_schema)}"
            )

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
        spans: list[Any],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        assertion_runs: list[dict[str, Any]] = []
        evaluator_scores_list: list[dict[str, Any]] = []

        # Extract usage metrics from spans
        usage_metrics = self._extract_usage_from_spans(spans)

        for eval_result in eval_results:
            # Skip results for evaluators not in the provided dict
            # (happens when processing mixed coded/legacy eval sets)
            if eval_result.evaluator_id not in evaluators:
                continue

            # Legacy API expects evaluatorId as GUID, convert string to GUID
            try:
                uuid.UUID(eval_result.evaluator_id)
                evaluator_id_value = eval_result.evaluator_id
            except ValueError:
                # Generate deterministic UUID5 from string
                evaluator_id_value = str(
                    uuid.uuid5(uuid.NAMESPACE_DNS, eval_result.evaluator_id)
                )

            # Convert BaseModel justification to JSON string for API compatibility
            justification = self._serialize_justification(eval_result.result.details)

            evaluator_scores_list.append(
                {
                    "type": eval_result.result.score_type.value,
                    "value": eval_result.result.score,
                    "justification": justification,
                    "evaluatorId": evaluator_id_value,
                }
            )
            assertion_runs.append(
                {
                    "status": EvaluationStatus.COMPLETED.value,
                    "evaluatorId": evaluator_id_value,
                    "completionMetrics": {
                        "duration": int(eval_result.result.evaluation_time)
                        if eval_result.result.evaluation_time
                        else 0,
                        "cost": usage_metrics["cost"],
                        "tokens": usage_metrics["tokens"] or 0,
                        "completionTokens": usage_metrics["completionTokens"] or 0,
                        "promptTokens": usage_metrics["promptTokens"] or 0,
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
        evaluators: dict[str, BaseEvaluator[Any, Any, Any]],
        spans: list[Any],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Collect results for coded evaluators.

        Returns evaluatorRuns and scores in the format expected by coded eval endpoints.
        """
        evaluator_runs: list[dict[str, Any]] = []
        evaluator_scores_list: list[dict[str, Any]] = []

        # Extract usage metrics from spans
        usage_metrics = self._extract_usage_from_spans(spans)

        for eval_result in eval_results:
            # Skip results for evaluators not in the provided dict
            # (happens when processing mixed coded/legacy eval sets)
            if eval_result.evaluator_id not in evaluators:
                continue

            # Convert BaseModel justification to JSON string for API compatibility
            justification = self._serialize_justification(eval_result.result.details)

            evaluator_scores_list.append(
                {
                    "type": eval_result.result.score_type.value,
                    "value": eval_result.result.score,
                    "justification": justification,
                    "evaluatorId": eval_result.evaluator_id,
                }
            )
            evaluator_runs.append(
                {
                    "status": EvaluationStatus.COMPLETED.value,
                    "evaluatorId": eval_result.evaluator_id,
                    "result": {
                        "score": {
                            "type": eval_result.result.score_type.value,
                            "value": eval_result.result.score,
                        },
                        "justification": justification,
                    },
                    "completionMetrics": {
                        "duration": int(eval_result.result.evaluation_time)
                        if eval_result.result.evaluation_time
                        else 0,
                        "cost": usage_metrics["cost"],
                        "tokens": usage_metrics["tokens"] or 0,
                        "completionTokens": usage_metrics["completionTokens"] or 0,
                        "promptTokens": usage_metrics["promptTokens"] or 0,
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
        success: bool,
        is_coded: bool = False,
    ) -> RequestSpec:
        # For legacy evaluations, endpoint is without /coded
        endpoint_suffix = "coded/" if is_coded else ""

        # Determine status based on success
        status = EvaluationStatus.COMPLETED if success else EvaluationStatus.FAILED

        inner_payload: dict[str, Any] = {
            "evalRunId": eval_run_id,
            # Backend expects integer status
            "status": status.value,
            "result": {
                "output": dict(actual_output),
                "evaluatorScores": evaluator_scores,
            },
            "completionMetrics": {"duration": int(execution_time)},
            "assertionRuns": assertion_runs,
        }

        # Legacy backend expects payload wrapped in "request" field
        # Coded backend accepts payload directly
        # Both coded and legacy send payload directly at root level
        payload = inner_payload

        # Log the payload for debugging eval run updates
        agent_type = "coded" if is_coded else "low-code"
        logger.debug(
            f"Updating eval run (type={agent_type}): "
            f"evalRunId={eval_run_id}, success={success}"
        )
        logger.debug(f"Full eval run update payload: {json.dumps(payload, indent=2)}")

        return RequestSpec(
            method="PUT",
            endpoint=Endpoint(
                f"{self._get_endpoint_prefix()}execution/agents/{self._project_id}/{endpoint_suffix}evalRun"
            ),
            json=payload,
            headers=self._tenant_header(),
        )

    def _update_coded_eval_run_spec(
        self,
        evaluator_runs: list[dict[str, Any]],
        evaluator_scores: list[dict[str, Any]],
        eval_run_id: str,
        actual_output: dict[str, Any],
        execution_time: float,
        success: bool,
        is_coded: bool = False,
    ) -> RequestSpec:
        """Create update spec for coded evaluators."""
        # For coded evaluations, endpoint has /coded
        endpoint_suffix = "coded/" if is_coded else ""

        # Determine status based on success
        status = EvaluationStatus.COMPLETED if success else EvaluationStatus.FAILED

        payload: dict[str, Any] = {
            "evalRunId": eval_run_id,
            # For coded evaluations, use integer status; for legacy, use string
            "status": status.value,
            "result": {
                "output": dict(actual_output),
                "scores": evaluator_scores,
            },
            "completionMetrics": {"duration": int(execution_time)},
            "evaluatorRuns": evaluator_runs,
        }

        # Log the payload for debugging coded eval run updates
        agent_type = "coded" if is_coded else "low-code"
        logger.debug(
            f"Updating coded eval run (type={agent_type}): "
            f"evalRunId={eval_run_id}, success={success}"
        )
        logger.debug(
            f"Full coded eval run update payload: {json.dumps(payload, indent=2)}"
        )

        return RequestSpec(
            method="PUT",
            endpoint=Endpoint(
                f"{self._get_endpoint_prefix()}execution/agents/{self._project_id}/{endpoint_suffix}evalRun"
            ),
            json=payload,
            headers=self._tenant_header(),
        )

    def _create_eval_run_spec(
        self, eval_item: EvaluationItem, eval_set_run_id: str, is_coded: bool = False
    ) -> RequestSpec:
        # Legacy API expects eval IDs as GUIDs, coded accepts strings
        # Convert string IDs to deterministic GUIDs for legacy
        if is_coded:
            eval_item_id = eval_item.id
        else:
            # Try to parse as GUID, if it fails, generate deterministic GUID from string
            try:
                uuid.UUID(eval_item.id)
                eval_item_id = eval_item.id
            except ValueError:
                # Generate deterministic UUID5 from string
                eval_item_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, eval_item.id))

        # Build eval snapshot based on evaluation item type
        eval_snapshot = {
            "id": eval_item_id,
            "name": eval_item.name,
            "inputs": eval_item.inputs,
        }

        # For coded evaluators, use evaluationCriterias directly
        # For legacy evaluators, extract expectedOutput from the migrated evaluationCriterias
        # (Legacy evals are migrated to EvaluationItem format with expectedOutput inside evaluationCriterias)
        if is_coded:
            eval_snapshot["evaluationCriterias"] = eval_item.evaluation_criterias
        else:
            # Legacy backend endpoint expects expectedOutput directly in evalSnapshot
            # Extract it from the first evaluator criteria (all criteria have the same expectedOutput)
            expected_output = {}
            if eval_item.evaluation_criterias:
                first_criteria = next(
                    iter(eval_item.evaluation_criterias.values()), None
                )
                if first_criteria and isinstance(first_criteria, dict):
                    expected_output = first_criteria.get("expectedOutput", {})
            eval_snapshot["expectedOutput"] = expected_output

        # For legacy evaluations, endpoint is without /coded
        endpoint_suffix = "coded/" if is_coded else ""

        inner_payload: dict[str, Any] = {
            "evalSetRunId": eval_set_run_id,
            "evalSnapshot": eval_snapshot,
            # Backend expects integer status
            "status": EvaluationStatus.IN_PROGRESS.value,
        }

        # Legacy backend expects payload wrapped in "request" field
        # Coded backend accepts payload directly
        # Both coded and legacy send payload directly at root level
        payload = inner_payload

        # Log the payload for debugging eval run reporting
        agent_type = "coded" if is_coded else "low-code"
        logger.debug(
            f"Creating eval run (type={agent_type}): "
            f"evalSetRunId={eval_set_run_id}, evalItemId={eval_item.id}"
        )
        logger.debug(f"Full eval run payload: {json.dumps(payload, indent=2)}")

        return RequestSpec(
            method="POST",
            endpoint=Endpoint(
                f"{self._get_endpoint_prefix()}execution/agents/{self._project_id}/{endpoint_suffix}evalRun"
            ),
            json=payload,
            headers=self._tenant_header(),
        )

    def _create_eval_set_run_spec(
        self,
        eval_set_id: str,
        agent_snapshot: StudioWebAgentSnapshot,
        no_of_evals: int,
        is_coded: bool = False,
    ) -> RequestSpec:
        # For legacy evaluations, endpoint is without /coded
        endpoint_suffix = "coded/" if is_coded else ""

        # Legacy API expects evalSetId as GUID, coded accepts string
        # Convert string IDs to deterministic GUIDs for legacy
        if is_coded:
            eval_set_id_value = eval_set_id
        else:
            # Try to parse as GUID, if it fails, generate deterministic GUID from string
            try:
                uuid.UUID(eval_set_id)
                eval_set_id_value = eval_set_id
            except ValueError:
                # Generate deterministic UUID5 from string
                eval_set_id_value = str(uuid.uuid5(uuid.NAMESPACE_DNS, eval_set_id))

        inner_payload: dict[str, Any] = {
            "agentId": self._project_id,
            "evalSetId": eval_set_id_value,
            "agentSnapshot": agent_snapshot.model_dump(by_alias=True),
            # Backend expects integer status
            "status": EvaluationStatus.IN_PROGRESS.value,
            "numberOfEvalsExecuted": no_of_evals,
            # Source is required by the backend (0 = coded SDK)
            "source": 0,
        }

        # Both coded and legacy send payload directly at root level
        payload = inner_payload

        # Log the payload for debugging eval set run reporting
        agent_type = "coded" if is_coded else "low-code"
        logger.info(
            f"Creating eval set run (type={agent_type}): "
            f"evalSetId={eval_set_id}, "
            f"inputSchema={json.dumps(payload.get('agentSnapshot', {}).get('inputSchema', {}))}, "
            f"outputSchema={json.dumps(payload.get('agentSnapshot', {}).get('outputSchema', {}))}"
        )
        logger.debug(f"Full eval set run payload: {json.dumps(payload, indent=2)}")

        return RequestSpec(
            method="POST",
            endpoint=Endpoint(
                f"{self._get_endpoint_prefix()}execution/agents/{self._project_id}/{endpoint_suffix}evalSetRun"
            ),
            json=payload,
            headers=self._tenant_header(),
        )

    def _update_eval_set_run_spec(
        self,
        eval_set_run_id: str,
        evaluator_scores: dict[str, float],
        is_coded: bool = False,
        success: bool = True,
    ) -> RequestSpec:
        # Legacy API expects evaluatorId as GUID, coded accepts string
        evaluator_scores_list = []
        for evaluator_id, avg_score in evaluator_scores.items():
            if is_coded:
                evaluator_id_value = evaluator_id
            else:
                # Convert string to GUID for legacy
                try:
                    uuid.UUID(evaluator_id)
                    evaluator_id_value = evaluator_id
                except ValueError:
                    # Generate deterministic UUID5 from string
                    evaluator_id_value = str(
                        uuid.uuid5(uuid.NAMESPACE_DNS, evaluator_id)
                    )

            evaluator_scores_list.append(
                {"value": avg_score, "evaluatorId": evaluator_id_value}
            )

        # For legacy evaluations, endpoint is without /coded
        endpoint_suffix = "coded/" if is_coded else ""

        # Determine status based on success
        status = EvaluationStatus.COMPLETED if success else EvaluationStatus.FAILED

        inner_payload: dict[str, Any] = {
            "evalSetRunId": eval_set_run_id,
            # Backend expects integer status
            "status": status.value,
            "evaluatorScores": evaluator_scores_list,
        }

        # Legacy backend expects payload wrapped in "request" field
        # Coded backend accepts payload directly
        # Both coded and legacy send payload directly at root level
        payload = inner_payload

        # Log the payload for debugging eval set run updates
        agent_type = "coded" if is_coded else "low-code"
        logger.info(
            f"Updating eval set run (type={agent_type}): "
            f"evalSetRunId={eval_set_run_id}, success={success}, "
            f"evaluatorScores={json.dumps(payload.get('evaluatorScores', []))}"
        )
        logger.debug(
            f"Full eval set run update payload: {json.dumps(payload, indent=2)}"
        )

        return RequestSpec(
            method="PUT",
            endpoint=Endpoint(
                f"{self._get_endpoint_prefix()}execution/agents/{self._project_id}/{endpoint_suffix}evalSetRun"
            ),
            json=payload,
            headers=self._tenant_header(),
        )

    def _get_eval_runs_spec(
        self,
        eval_set_id: str,
        eval_set_run_id: str,
        evaluation_id: str | None = None,
        is_coded: bool = False,
    ) -> RequestSpec:
        """Create request spec to GET eval runs for a given eval_set_run_id.

        Args:
            eval_set_id: The ID of the eval set
            eval_set_run_id: The ID of the eval set run
            evaluation_id: Optional evaluation ID to filter for a specific eval run
            is_coded: Whether this is a coded evaluation (vs legacy)

        Returns:
            RequestSpec for the GET request
        """
        # Build endpoint path matching backend structure:
        # Legacy: api/execution/agents/{agentId}/evalSets/{evalSetId}/evalSetRuns/{evalSetRunId}/evalRuns
        # Coded: api/execution/agents/{agentId}/coded/evalSets/{evalSetId}/evalSetRuns/{evalSetRunId}/evalRuns

        prefix = self._get_endpoint_prefix()

        if is_coded:
            endpoint_path = (
                f"{prefix}execution/agents/{self._project_id}/coded/"
                f"evalSets/{eval_set_id}/evalSetRuns/{eval_set_run_id}/evalRuns"
            )
        else:
            endpoint_path = (
                f"{prefix}execution/agents/{self._project_id}/"
                f"evalSets/{eval_set_id}/evalSetRuns/{eval_set_run_id}/evalRuns"
            )

        logger.debug(
            f"Creating GET eval runs spec: eval_set_id={eval_set_id}, "
            f"eval_set_run_id={eval_set_run_id}, evaluation_id={evaluation_id}, coded={is_coded}"
        )

        return RequestSpec(
            method="GET",
            endpoint=Endpoint(endpoint_path),
            params={},  # No query params needed - evalSetRunId is in the path
            headers=self._tenant_header(),
        )

    def _tenant_header(self) -> dict[str, str | None]:
        tenant_id = os.getenv(ENV_TENANT_ID, None)
        if not tenant_id:
            self._console.error(
                f"{ENV_TENANT_ID} env var is not set. Please run 'uipath auth'."
            )
        return {HEADER_INTERNAL_TENANT_ID: tenant_id}
