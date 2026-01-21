import logging
import os
import time
import uuid
from functools import wraps
from typing import Any, Callable, Dict, Optional

from uipath.telemetry._track import (
    is_telemetry_enabled,
    track_cli_event,
)

logger = logging.getLogger(__name__)

# Telemetry event name templates for Application Insights
CLI_COMMAND_STARTED = "Cli.{command}.Start.URT"
CLI_COMMAND_COMPLETED = "Cli.{command}.End.URT"
CLI_COMMAND_FAILED = "Cli.{command}.Failed.URT"


class CliTelemetryTracker:
    """Tracks CLI command execution and sends telemetry to Application Insights.

    This class handles tracking of CLI command lifecycle events:
    - Command start events
    - Command completion events (success)
    - Command failure events (with error details)
    """

    def __init__(self) -> None:
        self._start_times: Dict[str, float] = {}
        self._event_ids: Dict[str, str] = {}

    @staticmethod
    def _get_event_name(command: str, status: str) -> str:
        return f"Cli.{command.capitalize()}.{status}.URT"

    def _enrich_properties(self, properties: Dict[str, Any]) -> None:
        """Enrich properties with common context information.

        Args:
            properties: The properties dictionary to enrich.
        """
        # Add CI environment detection
        properties["IsCI"] = bool(os.getenv("GITHUB_ACTIONS"))

        # Add UiPath context
        project_id = os.getenv("UIPATH_PROJECT_ID")
        if project_id:
            properties["ProjectId"] = project_id

        org_id = os.getenv("UIPATH_CLOUD_ORGANIZATION_ID")
        if org_id:
            properties["CloudOrganizationId"] = org_id

        user_id = os.getenv("UIPATH_CLOUD_USER_ID")
        if user_id:
            properties["CloudUserId"] = user_id

        tenant_id = os.getenv("UIPATH_TENANT_ID")
        if tenant_id:
            properties["TenantId"] = tenant_id

        # Add source identifier
        properties["Source"] = "uipath-python-cli"
        properties["ApplicationName"] = "UiPath.Cli"

    def track_command_start(self, command: str) -> None:
        try:
            self._start_times[command] = time.time()
            self._event_ids[command] = str(uuid.uuid4())

            properties: Dict[str, Any] = {
                "Command": command,
                "EventId": self._event_ids[command],
            }
            self._enrich_properties(properties)

            track_cli_event(self._get_event_name(command, "Start"), properties)
            logger.debug(f"Tracked CLI command started: {command}")

        except Exception as e:
            logger.debug(f"Error tracking CLI command start: {e}")

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

            event_id = self._event_ids.pop(command, None)

            properties: Dict[str, Any] = {
                "Command": command,
                "Success": True,
            }

            if event_id:
                properties["EventId"] = event_id

            if duration_ms is not None:
                properties["DurationMs"] = duration_ms

            self._enrich_properties(properties)

            track_cli_event(self._get_event_name(command, "End"), properties)
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

            event_id = self._event_ids.pop(command, None)

            properties: Dict[str, Any] = {
                "Command": command,
                "Success": False,
            }

            if event_id:
                properties["EventId"] = event_id

            if duration_ms is not None:
                properties["DurationMs"] = duration_ms

            if exception is not None:
                properties["ErrorType"] = type(exception).__name__
                properties["ErrorMessage"] = str(exception)[:500]

            self._enrich_properties(properties)

            track_cli_event(self._get_event_name(command, "Failed"), properties)
            logger.debug(f"Tracked CLI command failed: {command}")

        except Exception as e:
            logger.debug(f"Error tracking CLI command failed: {e}")


def track_command(command: str) -> Callable[..., Any]:
    """Decorator to track CLI command execution.

    Tracks the following events to Application Insights:
    - Cli.<Command>.Start.URT - when command begins
    - Cli.<Command>.End.URT - on successful completion
    - Cli.<Command>.Failed.URT - on exception

    Properties tracked include:
    - Command: The command name
    - Success: Whether the command succeeded
    - DurationMs: Execution time in milliseconds
    - ErrorType: Exception type name (on failure)
    - ErrorMessage: Exception message (on failure, truncated to 500 chars)
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
            if not is_telemetry_enabled():
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
