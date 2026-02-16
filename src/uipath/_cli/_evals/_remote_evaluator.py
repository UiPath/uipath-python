"""Remote evaluation client for submitting evaluations to the C# Agents backend."""

import asyncio
import logging
import os
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from uipath._utils import Endpoint, RequestSpec
from uipath._utils.constants import ENV_EVAL_BACKEND_URL, ENV_TENANT_ID, HEADER_INTERNAL_TENANT_ID
from uipath.eval.models.serializable_span import SerializableSpan
from uipath.platform import UiPath

logger = logging.getLogger(__name__)


# --- Request/Response Models ---


class EvaluatorConfigPayload(BaseModel):
    """Evaluator configuration for the remote evaluation request."""

    id: str
    version: str = "1.0"
    evaluator_type_id: str = Field(alias="evaluatorTypeId")
    evaluator_config: dict[str, Any] = Field(default_factory=dict, alias="evaluatorConfig")
    evaluator_schema: str = Field(default="", alias="evaluatorSchema")

    model_config = {"populate_by_name": True}


class EvaluationItemPayload(BaseModel):
    """Individual evaluation item in the remote evaluation request."""

    id: str
    name: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    evaluation_criterias: dict[str, dict[str, Any] | None] = Field(
        default_factory=dict, alias="evaluationCriterias"
    )
    expected_agent_behavior: str = Field(default="", alias="expectedAgentBehavior")
    agent_output: dict[str, Any] | str | None = Field(default=None, alias="agentOutput")
    agent_execution_time: float = Field(default=0.0, alias="agentExecutionTime")
    serialized_traces: list[SerializableSpan] = Field(
        default_factory=list, alias="serializedTraces"
    )
    agent_error: str | None = Field(default=None, alias="agentError")
    eval_run_id: str | None = Field(default=None, alias="evalRunId")

    model_config = {"populate_by_name": True}


class RemoteEvaluationRequest(BaseModel):
    """Request payload for POST /api/evaluate."""

    eval_set_run_id: str = Field(alias="evalSetRunId")
    eval_set_id: str = Field(alias="evalSetId")
    project_id: str = Field(alias="projectId")
    entrypoint: str = ""
    is_coded: bool = Field(default=True, alias="isCoded")
    report_to_studio_web: bool = Field(default=True, alias="reportToStudioWeb")
    evaluator_configs: list[EvaluatorConfigPayload] = Field(
        default_factory=list, alias="evaluatorConfigs"
    )
    evaluation_items: list[EvaluationItemPayload] = Field(
        default_factory=list, alias="evaluationItems"
    )

    model_config = {"populate_by_name": True}


class RemoteJobStatus(str, Enum):
    """Status values for a remote evaluation job."""

    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"


class EvaluatorResultPayload(BaseModel):
    """Single evaluator result from the remote backend."""

    evaluator_id: str = Field(alias="evaluatorId")
    score: float = 0.0
    score_type: int = Field(default=0, alias="scoreType")
    details: str | None = None
    evaluation_time: float = Field(default=0.0, alias="evaluationTime")

    model_config = {"populate_by_name": True}


class EvaluationItemResultPayload(BaseModel):
    """Results for a single evaluation item from the remote backend."""

    evaluation_item_id: str = Field(alias="evaluationItemId")
    evaluator_results: list[EvaluatorResultPayload] = Field(
        default_factory=list, alias="evaluatorResults"
    )
    success: bool = True

    model_config = {"populate_by_name": True}


class RemoteEvaluationSubmitResponse(BaseModel):
    """Response from POST /api/evaluate."""

    evaluation_job_id: str = Field(alias="evaluationJobId")
    status: RemoteJobStatus = RemoteJobStatus.PENDING

    model_config = {"populate_by_name": True}


class RemoteEvaluationStatusResponse(BaseModel):
    """Response from GET /api/evaluate/status/{id}."""

    evaluation_job_id: str = Field(alias="evaluationJobId")
    status: RemoteJobStatus
    results: list[EvaluationItemResultPayload] = Field(default_factory=list)
    evaluator_averages: dict[str, float] = Field(
        default_factory=dict, alias="evaluatorAverages"
    )
    error: str | None = None

    model_config = {"populate_by_name": True}


# --- Client ---


class RemoteEvaluationClient:
    """Client for submitting evaluations to the remote C# Agents backend.

    The backend runs evaluators via Temporal workflows and reports results
    to Studio Web, decoupling evaluation execution from the CLI process.
    """

    def __init__(self, backend_url: str | None = None):
        eval_backend_url = backend_url or os.getenv(ENV_EVAL_BACKEND_URL)
        uipath = UiPath(base_url=eval_backend_url) if eval_backend_url else UiPath()
        self._client = uipath.api_client
        self._backend_url = eval_backend_url

    def _get_endpoint_prefix(self) -> str:
        """Determine the endpoint prefix based on environment."""
        if self._backend_url:
            from urllib.parse import urlparse

            try:
                parsed = urlparse(self._backend_url)
                hostname = parsed.hostname or parsed.netloc.split(":")[0]
                if hostname.lower() in ("localhost", "127.0.0.1"):
                    return "api/"
            except Exception:
                pass
        return "agentsruntime_/api/"

    def _tenant_header(self) -> dict[str, str | None]:
        tenant_id = os.getenv(ENV_TENANT_ID, None)
        return {HEADER_INTERNAL_TENANT_ID: tenant_id}

    def _is_localhost(self) -> bool:
        if self._backend_url:
            from urllib.parse import urlparse

            try:
                parsed = urlparse(self._backend_url)
                hostname = parsed.hostname or parsed.netloc.split(":")[0]
                return hostname.lower() in ("localhost", "127.0.0.1")
            except Exception:
                pass
        return False

    async def submit_evaluation(
        self, request: RemoteEvaluationRequest
    ) -> RemoteEvaluationSubmitResponse:
        """Submit an evaluation job to the remote backend.

        Args:
            request: The evaluation request payload.

        Returns:
            Response with the evaluation job ID and initial status.

        Raises:
            Exception: If the backend is unreachable or returns an error.
        """
        prefix = self._get_endpoint_prefix()
        spec = RequestSpec(
            method="POST",
            endpoint=Endpoint(f"{prefix}evaluate"),
            json=request.model_dump(by_alias=True),
            headers=self._tenant_header(),
        )

        logger.info(
            f"Submitting remote evaluation: eval_set_run_id={request.eval_set_run_id}, "
            f"items={len(request.evaluation_items)}, evaluators={len(request.evaluator_configs)}"
        )

        response = await self._client.request_async(
            method=spec.method,
            url=spec.endpoint,
            json=spec.json,
            headers=spec.headers,
            scoped="org" if self._is_localhost() else "tenant",
        )

        import json

        response_data = json.loads(response.content)
        result = RemoteEvaluationSubmitResponse.model_validate(response_data)

        logger.info(
            f"Remote evaluation submitted: job_id={result.evaluation_job_id}, "
            f"status={result.status}"
        )
        return result

    async def poll_status(
        self,
        job_id: str,
        timeout: float = 600.0,
        initial_interval: float = 1.0,
        max_interval: float = 10.0,
    ) -> RemoteEvaluationStatusResponse:
        """Poll the remote backend for evaluation job status until completion.

        Uses exponential backoff for polling interval.

        Args:
            job_id: The evaluation job ID to poll.
            timeout: Maximum time in seconds to wait for completion.
            initial_interval: Initial polling interval in seconds.
            max_interval: Maximum polling interval in seconds.

        Returns:
            The final status response with results.

        Raises:
            TimeoutError: If the job does not complete within the timeout.
            Exception: If the job fails or consecutive network errors occur.
        """
        prefix = self._get_endpoint_prefix()
        elapsed = 0.0
        interval = initial_interval
        consecutive_errors = 0
        max_consecutive_errors = 5

        terminal_statuses = {
            RemoteJobStatus.COMPLETED,
            RemoteJobStatus.FAILED,
            RemoteJobStatus.PARTIALLY_COMPLETED,
        }

        while elapsed < timeout:
            try:
                spec = RequestSpec(
                    method="GET",
                    endpoint=Endpoint(f"{prefix}evaluate/status/{job_id}"),
                    headers=self._tenant_header(),
                )

                response = await self._client.request_async(
                    method=spec.method,
                    url=spec.endpoint,
                    headers=spec.headers,
                    scoped="org" if self._is_localhost() else "tenant",
                )

                import json

                response_data = json.loads(response.content)
                status_response = RemoteEvaluationStatusResponse.model_validate(
                    response_data
                )

                consecutive_errors = 0  # Reset on success

                logger.debug(
                    f"Poll status for job {job_id}: status={status_response.status}"
                )

                if status_response.status in terminal_statuses:
                    logger.info(
                        f"Remote evaluation job {job_id} reached terminal status: "
                        f"{status_response.status}"
                    )
                    return status_response

            except Exception as e:
                consecutive_errors += 1
                logger.warning(
                    f"Error polling evaluation status (attempt {consecutive_errors}/"
                    f"{max_consecutive_errors}): {e}"
                )
                if consecutive_errors >= max_consecutive_errors:
                    raise RuntimeError(
                        f"Failed to poll evaluation status after {max_consecutive_errors} "
                        f"consecutive errors. Last error: {e}"
                    ) from e

            await asyncio.sleep(interval)
            elapsed += interval
            # Exponential backoff with cap
            interval = min(interval * 1.5, max_interval)

        raise TimeoutError(
            f"Remote evaluation job {job_id} did not complete within {timeout}s. "
            f"You can check the status manually using the job ID."
        )
