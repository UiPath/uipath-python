import logging
import os
import time
from functools import wraps
from importlib.metadata import version
from typing import Any, Callable, Dict, Optional

from uipath._cli._utils._common import get_claim_from_token
from uipath.telemetry._track import (
    _get_project_key,
    is_telemetry_enabled,
    track_cli_event,
)

logger = logging.getLogger(__name__)

# Telemetry event name template for Application Insights
CLI_COMMAND_EVENT = "Cli.{command}"


class CliTelemetryTracker:
    """Tracks CLI command execution and sends telemetry to Application Insights.

    Sends a single event per command execution at completion with:
    - Status: "Completed" or "Failed"
    - Success: Boolean indicating success/failure
    - Error details (if failed)
    """

    def __init__(self) -> None:
        self._start_times: Dict[str, float] = {}

    @staticmethod
    def _get_event_name(command: str) -> str:
        return f"Cli.{command.capitalize()}"

    def _enrich_properties(self, properties: Dict[str, Any]) -> None:
        """Enrich properties with common context information.

        Args:
            properties: The properties dictionary to enrich.
        """
        # Add UiPath context
        project_key = _get_project_key()
        if project_key:
            properties["AgentId"] = project_key

        # Get organization ID
        organization_id = os.getenv("UIPATH_ORGANIZATION_ID")
        if organization_id:
            properties["CloudOrganizationId"] = organization_id

        # Get tenant ID
        tenant_id = os.getenv("UIPATH_TENANT_ID")
        if tenant_id:
            properties["CloudTenantId"] = tenant_id

        # Get CloudUserId from JWT token
        try:
            cloud_user_id = get_claim_from_token("sub")
            if cloud_user_id:
                properties["CloudUserId"] = cloud_user_id
        except Exception:
            pass

        properties["SessionId"] = "nosession"  # Placeholder for session ID

        try:
            properties["SDKVersion"] = version("uipath")
        except Exception:
            pass

        properties["IsGithubCI"] = bool(os.getenv("GITHUB_ACTIONS"))

        # Add source identifier
        properties["Source"] = "uipath-python-cli"
        properties["ApplicationName"] = "UiPath.AgentCli"

    def track_command_start(self, command: str) -> None:
        """Record the start time for duration calculation."""
        try:
            self._start_times[command] = time.time()
            logger.debug(f"Started tracking CLI command: {command}")

        except Exception as e:
            logger.debug(f"Error recording CLI command start time: {e}")

    def track_command_end(
        self,
        command: str,
        duration_ms: Optional[int] = None,
    ) -> None:
        try:
            if duration_ms is None:
                start_time = self._start_times.pop(command, None)
                if start_time:
                    duration_ms = int((time.time() - start_time) * 1000)

            properties: Dict[str, Any] = {
                "Command": command,
                "Status": "Completed",
                "Success": True,
            }

            if duration_ms is not None:
                properties["DurationMs"] = duration_ms

            self._enrich_properties(properties)

            track_cli_event(self._get_event_name(command), properties)
            logger.debug(f"Tracked CLI command completed: {command}")

        except Exception as e:
            logger.debug(f"Error tracking CLI command end: {e}")

    def track_command_failed(
        self,
        command: str,
        duration_ms: Optional[int] = None,
        exception: Optional[Exception] = None,
    ) -> None:
        try:
            if duration_ms is None:
                start_time = self._start_times.pop(command, None)
                if start_time:
                    duration_ms = int((time.time() - start_time) * 1000)

            properties: Dict[str, Any] = {
                "Command": command,
                "Status": "Failed",
                "Success": False,
            }

            if duration_ms is not None:
                properties["DurationMs"] = duration_ms

            if exception is not None:
                properties["ErrorType"] = type(exception).__name__
                properties["ErrorMessage"] = str(exception)[:500]

            self._enrich_properties(properties)

            track_cli_event(self._get_event_name(command), properties)
            logger.debug(f"Tracked CLI command failed: {command}")

        except Exception as e:
            logger.debug(f"Error tracking CLI command failed: {e}")


def track_command(command: str) -> Callable[..., Any]:
    """Decorator to track CLI command execution.

    Sends an event (Cli.<Command>) to Application Insights at command
    completion with the execution outcome.

    Properties tracked include:
    - Command: The command name
    - Status: Execution outcome ("Completed" or "Failed")
    - Success: Whether the command succeeded (true/false)
    - DurationMs: Execution time in milliseconds
    - ErrorType: Exception type name (on failure)
    - ErrorMessage: Exception message (on failure, truncated to 500 chars)
    - AgentId: Project key from .uipath/.telemetry.json (GUID)
    - Version: Package version (uipath package)
    - ProjectId, CloudOrganizationId, etc. (if available)

    Telemetry failures are silently ignored to ensure CLI execution
    is never blocked by telemetry issues.

    Args:
        command: The CLI command name (e.g., "pack", "publish", "run").

    Returns:
        A decorator function that wraps the CLI command.

    Example:
        @click.command()
        @track_command("pack")
        def pack(root, nolock):
            ...
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not is_telemetry_enabled() or os.getenv("UIPATH_JOB_KEY"):
                return func(*args, **kwargs)

            tracker = CliTelemetryTracker()
            tracker.track_command_start(command)

            try:
                result = func(*args, **kwargs)
                tracker.track_command_end(command)
                return result

            except Exception as e:
                tracker.track_command_failed(command, exception=e)
                raise

        return wrapper

    return decorator
