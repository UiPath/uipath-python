"""
Core runtime contracts that define the interfaces between components.
"""

import sys
import traceback
from enum import Enum
from typing import Any, Dict, Optional, Union

from pydantic import BaseModel, Field


class RuntimeStatus(str, Enum):
    """Standard status values for runtime execution."""

    SUCCESSFUL = "successful"
    FAULTED = "faulted"
    SUSPENDED = "suspended"


class ResumeTrigger(str, Enum):
    """
    Constants representing different types of resume job triggers in the system.
    """

    NONE = "None"
    QUEUE_ITEM = "QueueItem"
    JOB = "Job"
    ACTION = "Task"
    TIMER = "Timer"
    INBOX = "Inbox"
    API = "Api"


class ApiTriggerInfo(BaseModel):
    """API resume trigger request."""

    inbox_id: Optional[str] = Field(default=None, alias="inboxId")
    request: Any = None

    model_config = {"populate_by_name": True}


class ResumeInfo(BaseModel):
    """Information needed to resume execution."""

    trigger_type: ResumeTrigger = Field(default=ResumeTrigger.API, alias="triggerType")
    item_key: Optional[str] = Field(default=None, alias="itemKey")
    api_resume: Optional[ApiTriggerInfo] = Field(default=None, alias="apiResume")

    model_config = {"populate_by_name": True}


class RuntimeContext(BaseModel):
    """Context information passed throughout the runtime execution."""

    entrypoint: Optional[str] = None
    input: Optional[str] = None
    input_json: Optional[Any] = None
    job_id: Optional[str] = None
    trace_id: Optional[str] = None
    tracing_enabled: Union[bool, str] = False
    resume: bool = False
    config_path: str = "uipath.json"
    runtime_dir: Optional[str] = "__uipath"
    logs_file: Optional[str] = "execution.log"
    logs_min_level: Optional[str] = "INFO"
    output_file: str = "output.json"
    state_file: str = "state.db"

    model_config = {"arbitrary_types_allowed": True}

    @classmethod
    def from_config(cls, config_path=None):
        """
        Load configuration from uipath.json file.

        Args:
            config_path: Path to the configuration file. If None, uses the default "uipath.json"

        Returns:
            An instance of the class with fields populated from the config file
        """
        import json
        import os

        path = config_path or "uipath.json"

        config = {}

        if os.path.exists(path):
            with open(path, "r") as f:
                config = json.load(f)

        instance = cls()

        if "runtime" in config:
            runtime_config = config["runtime"]

            mapping = {
                "dir": "runtime_dir",
                "outputFile": "output_file",
                "stateFile": "state_file",
                "logsFile": "logs_file",
            }

            for config_key, attr_name in mapping.items():
                if config_key in runtime_config and hasattr(instance, attr_name):
                    setattr(instance, attr_name, runtime_config[config_key])

        return instance


class ErrorCategory(str, Enum):
    """Categories of runtime errors."""

    DEPLOYMENT = "Deployment"  # Configuration, licensing, or permission issues
    SYSTEM = "System"  # Unexpected internal errors or infrastructure issues
    UNKNOWN = "Unknown"  # Default category when the error type is not specified
    USER = "User"  # Business logic or domain-level errors


class ErrorInfo(BaseModel):
    """Standard error contract used across the runtime."""

    code: str  # Human-readable code uniquely identifying this error type across the platform.
    # Format: <Component>.<PascalCaseErrorCode> (e.g. LangGraph.InvaliGraphReference)
    # Only use alphanumeric characters [A-Za-z0-9] and periods. No whitespace allowed.

    title: str  # Short, human-readable summary of the problem that should remain consistent
    # across occurrences.

    detail: (
        str  # Human-readable explanation specific to this occurrence of the problem.
    )
    # May include context, recommended actions, or technical details like call stacks
    # for technical users.

    category: ErrorCategory = ErrorCategory.UNKNOWN  # Classification of the error:
    # - User: Business logic or domain-level errors
    # - Deployment: Configuration, licensing, or permission issues
    # - System: Unexpected internal errors or infrastructure issues

    status: Optional[int] = (
        None  # HTTP status code, if relevant (e.g., when forwarded from a web API)
    )


class ExecutionResult(BaseModel):
    """Result of an execution with status and optional error information."""

    output: Optional[Dict[str, Any]] = None
    status: RuntimeStatus = RuntimeStatus.SUCCESSFUL
    resume: Optional[ResumeInfo] = None
    error: Optional[ErrorInfo] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format for output."""
        result = {
            "output": self.output or {},
            "status": self.status,
        }

        if self.resume:
            result["resume"] = self.resume.model_dump(by_alias=True)

        if self.error:
            result["error"] = self.error.model_dump()

        return result


class UiPathRuntimeError(Exception):
    """Base exception class for UiPath runtime errors with structured error information."""

    def __init__(
        self,
        code: str,
        title: str,
        detail: str,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        status: Optional[int] = None,
        prefix: str = "Code",
        include_traceback: bool = True,
    ):
        # Get the current traceback as a string
        if include_traceback:
            tb = traceback.format_exc()
            if (
                tb and tb.strip() != "NoneType: None"
            ):  # Ensure there's an actual traceback
                detail = f"{detail}\n\nTraceback:\n{tb}"

        if status is None:
            status = self._extract_http_status()

        self.error_info = ErrorInfo(
            code=f"{prefix}.{code}",
            title=title,
            detail=detail,
            category=category,
            status=status,
        )
        super().__init__(detail)

    def _extract_http_status(self) -> Optional[int]:
        """Extract HTTP status code from the exception chain if present."""
        exc_info = sys.exc_info()
        if not exc_info or len(exc_info) < 2 or exc_info[1] is None:
            return None

        exc: Optional[BaseException] = exc_info[1]  # Current exception being handled
        while exc is not None:
            if hasattr(exc, "status_code"):
                return exc.status_code

            if hasattr(exc, "response") and hasattr(exc.response, "status_code"):
                return exc.response.status_code

            # Move to the next exception in the chain
            next_exc = getattr(exc, "__cause__", None) or getattr(
                exc, "__context__", None
            )

            # Ensure next_exc is a BaseException or None
            exc = (
                next_exc
                if isinstance(next_exc, BaseException) or next_exc is None
                else None
            )

        return None

    @property
    def as_dict(self) -> Dict[str, Any]:
        """Get the error information as a dictionary."""
        return self.error_info.model_dump()
