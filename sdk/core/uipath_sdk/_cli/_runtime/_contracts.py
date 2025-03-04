"""
Core runtime contracts that define the interfaces between components.
"""

import traceback
from enum import Enum
from typing import Any, Dict, Optional, Union

from pydantic import BaseModel, Field


class RuntimeStatus(str, Enum):
    """Standard status values for runtime execution."""

    SUCCESSFUL = "successful"
    FAULTED = "faulted"
    SUSPENDED = "suspended"


class ErrorCategory(str, Enum):
    """Categories of runtime errors."""

    DEPLOYMENT = "deployment"
    SYSTEM = "system"
    UNKNOWN = "unknown"
    USER = "user"


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


class ErrorInfo(BaseModel):
    """Standard error contract used across the runtime."""

    code: str
    title: str
    detail: str
    category: ErrorCategory = ErrorCategory.UNKNOWN
    status: Optional[int] = None


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
    logs_dir: Optional[str] = "__uipath_logs"
    logs_min_level: Optional[str] = "INFO"
    output_file: str = "__uipath_output.json"

    model_config = {"arbitrary_types_allowed": True}


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
        prefix: str = "CODE",
        include_traceback: bool = True,
    ):
        # Get the current traceback as a string
        if include_traceback:
            tb = traceback.format_exc()
            if (
                tb and tb.strip() != "NoneType: None"
            ):  # Ensure there's an actual traceback
                detail = f"{detail}\n\nTraceback:\n{tb}"

        self.error_info = ErrorInfo(
            code=f"{prefix}.{code}",
            title=title,
            detail=detail,
            category=category,
            status=status,
        )
        super().__init__(detail)

    @property
    def as_dict(self) -> Dict[str, Any]:
        """Get the error information as a dictionary."""
        return self.error_info.model_dump()
