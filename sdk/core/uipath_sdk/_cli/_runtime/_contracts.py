"""
Core runtime contracts that define the interfaces between components.
"""

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, Optional


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


@dataclass
class ErrorInfo:
    """Standard error contract used across the runtime."""

    code: str
    title: str
    detail: str
    category: ErrorCategory = ErrorCategory.UNKNOWN
    status: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary compatible with JobErrorDto."""
        return {
            "code": self.code,
            "title": self.title,
            "detail": self.detail,
            "category": self.category,
            "status": self.status,
        }


@dataclass
class ApiTriggerInfo:
    """API resume trigger request."""

    inboxId: Optional[str] = None
    request: Any = None


@dataclass
class ResumeInfo:
    """Information needed to resume execution."""

    triggerType: str = ResumeTrigger.API
    itemKey: Optional[str] = None
    apiResume: Optional[ApiTriggerInfo] = None


@dataclass
class RuntimeContext:
    """Context information passed throughout the runtime execution."""

    entrypoint: Optional[str] = None
    input: Optional[str] = None
    input_json: Any = None
    job_id: Optional[str] = None
    trace_id: Optional[str] = None
    tracing_enabled: bool = False
    resume: bool = False
    config_path: str = "uipath.json"
    logs_dir: Optional[str] = "__uipath_logs"
    output_file: str = "__uipath_output.json"


@dataclass
class ExecutionResult:
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
            result["resume"] = asdict(self.resume)

        if self.error:
            result["error"] = self.error.to_dict()

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
    ):
        self.error_info = ErrorInfo(f"{prefix}.{code}", title, detail, category, status)
        super().__init__(detail)

    @property
    def as_dict(self) -> Dict[str, Any]:
        """Get the error information as a dictionary."""
        return self.error_info.to_dict()
