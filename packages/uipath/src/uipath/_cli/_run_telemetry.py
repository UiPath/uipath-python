"""Lifecycle events for coded agent and coded function runs.

The coded counterpart to low-code's ``AgentRun.*``. Unlike ``Cli.*`` these are not
suppressed under a job key, so cloud runs report too.
"""

import logging
import os
import time
import uuid
from enum import Enum
from importlib.metadata import version
from typing import Any

from uipath.platform.common import UiPathConfig, resolve_trace_id
from uipath.platform.constants import ENV_IMAGE_VERSION, ENV_JOB_ID
from uipath.runtime.errors import UiPathBaseRuntimeError, UiPathErrorContract
from uipath.runtime.result import UiPathRuntimeResult, UiPathRuntimeStatus
from uipath.telemetry._track import is_telemetry_enabled, track_event

logger = logging.getLogger(__name__)

APPLICATION_NAME = "UiPath.CodedAgent"

SOURCE = "uipath-python-cli"

NOT_AVAILABLE = "N/A"

_LOWCODE_AGENT_TYPE = "uipath_lowcode"
_FUNCTION_FRAMEWORK = "python"


class RunKind(str, Enum):
    """Event-name prefix per run kind."""

    CODED_AGENT = "CodedAgentRun"
    CODED_FUNCTION = "CodedFunctionRun"


def classify_run(agent_type: str | None, agent_framework: str | None) -> RunKind | None:
    """Run kind from factory settings, or ``None`` when low-code owns the run.

    Both coded kinds report ``agent_type`` ``uipath_coded``, so only the framework
    separates them. A factory reporting nothing is assumed to wrap one.
    """
    if agent_type and agent_type.strip().lower() == _LOWCODE_AGENT_TYPE:
        return None
    if agent_framework and agent_framework.strip().lower() == _FUNCTION_FRAMEWORK:
        return RunKind.CODED_FUNCTION
    return RunKind.CODED_AGENT


def _cloud_user_id() -> str | None:
    if configured := UiPathConfig.cloud_user_id:
        return configured
    try:
        from uipath._cli._utils._common import get_claim_from_token

        return get_claim_from_token("sub")
    except Exception:
        return None


def _scope_properties() -> dict[str, Any]:
    """Identity and scope, on every event so each one stands alone.

    The cloud identity trio is required, so it reports ``N/A`` rather than being
    dropped; optional scope is omitted, so a local run has no folder.
    """
    properties: dict[str, Any] = {
        "FolderKey": UiPathConfig.folder_key,
        "JobKey": UiPathConfig.job_key,
        "JobId": os.getenv(ENV_JOB_ID),
        "CloudOrganizationId": UiPathConfig.organization_id or NOT_AVAILABLE,
        "CloudTenantId": UiPathConfig.tenant_id or NOT_AVAILABLE,
        "CloudUserId": _cloud_user_id() or NOT_AVAILABLE,
        "ProjectId": UiPathConfig.project_id,
        "ProjectKey": UiPathConfig.project_key,
        "ProcessName": UiPathConfig.process_key,
        "ProcessUuid": UiPathConfig.process_uuid,
        "ProcessVersion": UiPathConfig.process_version,
        "TraceId": resolve_trace_id(),
        "ImageVersion": os.getenv(ENV_IMAGE_VERSION),
    }
    return {key: value for key, value in properties.items() if value is not None}


def _error_properties(
    error_type: str | None, contract: UiPathErrorContract | None
) -> dict[str, Any]:
    """Error classification only, since message and traceback carry customer source.

    ``ErrorType`` is the exception class, so it is absent for a faulted result that
    never raised rather than borrowing the contract code.
    """
    properties: dict[str, Any] = {}
    if error_type:
        properties["ErrorType"] = error_type
    if contract is None:
        return properties
    properties["ErrorCode"] = contract.code
    properties["ErrorTitle"] = contract.title
    category = contract.category
    properties["ErrorCategory"] = getattr(category, "value", category)
    return properties


class RunTelemetry:
    """Emits Start and one terminal event for a single coded run."""

    def __init__(
        self,
        *,
        kind: RunKind,
        entrypoint: str | None,
        execution_source: str | None,
        is_conversational: bool,
    ) -> None:
        """Key the run on its job so a suspend/resume pair stays one run."""
        self._kind = kind
        self._entrypoint = entrypoint
        self._execution_source = execution_source
        self._is_conversational = is_conversational
        self._run_id = UiPathConfig.job_key or str(uuid.uuid4())
        self._started_at = time.monotonic()

    @classmethod
    def start(
        cls,
        *,
        agent_type: str | None,
        agent_framework: str | None,
        entrypoint: str | None,
        execution_source: str | None = None,
        is_conversational: bool = False,
    ) -> "RunTelemetry | None":
        """Emit Start and return a handle, or ``None`` when not reporting.

        ``None`` when telemetry is off, or for low-code, which reports itself.
        """
        if not is_telemetry_enabled():
            return None

        kind = classify_run(agent_type, agent_framework)
        if kind is None:
            return None

        instance = cls(
            kind=kind,
            entrypoint=entrypoint,
            execution_source=execution_source,
            is_conversational=is_conversational,
        )
        instance._emit("Start", {})
        return instance

    def finished(self, result: UiPathRuntimeResult | None) -> None:
        """Terminal event for a run that returned.

        Faulted failed without raising; suspended is waiting, not broken.
        """
        status = result.status if result else UiPathRuntimeStatus.SUCCESSFUL

        if status == UiPathRuntimeStatus.FAULTED:
            contract = result.error if result else None
            self._emit(
                "Failed",
                {"Status": "Failed", **_error_properties(None, contract)},
                include_duration=True,
            )
            return

        label = "Suspended" if status == UiPathRuntimeStatus.SUSPENDED else "Completed"
        self._emit("End", {"Status": label}, include_duration=True)

    def failed(self, exception: BaseException) -> None:
        """Terminal event for a run that raised."""
        contract = getattr(exception, "error_info", None)
        if not isinstance(exception, UiPathBaseRuntimeError):
            contract = None
        self._emit(
            "Failed",
            {
                "Status": "Failed",
                **_error_properties(type(exception).__name__, contract),
            },
            include_duration=True,
        )

    def _emit(
        self, suffix: str, extra: dict[str, Any], include_duration: bool = False
    ) -> None:
        try:
            properties: dict[str, Any] = {
                "AgentRunId": self._run_id,
                "AgentType": "Coded",
                "AgentRunSource": self._execution_source,
                "Entrypoint": self._entrypoint,
                "IsConversational": self._is_conversational,
                "Runtime": "URT",
                "ApplicationName": APPLICATION_NAME,
                "Source": SOURCE,
                "SDKVersion": version("uipath"),
            }
            properties = {
                key: value for key, value in properties.items() if value is not None
            }
            properties.update(_scope_properties())

            if include_duration:
                properties["DurationMs"] = int(
                    (time.monotonic() - self._started_at) * 1000
                )

            properties.update(extra)
            track_event(f"{self._kind.value}.{suffix}", properties)
        except Exception:
            logger.debug("Failed to emit %s run event", suffix, exc_info=True)
