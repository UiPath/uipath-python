"""
Core runtime contracts that define the interfaces between components.
"""

import json
import logging
import os
import sys
import traceback
from abc import ABC, abstractmethod
from enum import Enum
from functools import cached_property
from typing import Any, Dict, Optional, Union

from pydantic import BaseModel, Field

from uipath_sdk._cli._runtime._logging import LogsInterceptor

logger = logging.getLogger(__name__)


class UiPathResumeTriggerType(str, Enum):
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


class UiPathApiTrigger(BaseModel):
    """API resume trigger request."""

    inbox_id: Optional[str] = Field(default=None, alias="inboxId")
    request: Any = None

    model_config = {"populate_by_name": True}


class UiPathResumeTrigger(BaseModel):
    """Information needed to resume execution."""

    trigger_type: UiPathResumeTriggerType = Field(
        default=UiPathResumeTriggerType.API, alias="triggerType"
    )
    item_key: Optional[str] = Field(default=None, alias="itemKey")
    api_resume: Optional[UiPathApiTrigger] = Field(default=None, alias="apiResume")

    model_config = {"populate_by_name": True}


class UiPathErrorCategory(str, Enum):
    """Categories of runtime errors."""

    DEPLOYMENT = "Deployment"  # Configuration, licensing, or permission issues
    SYSTEM = "System"  # Unexpected internal errors or infrastructure issues
    UNKNOWN = "Unknown"  # Default category when the error type is not specified
    USER = "User"  # Business logic or domain-level errors


class UiPathErrorContract(BaseModel):
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

    category: UiPathErrorCategory = (
        UiPathErrorCategory.UNKNOWN
    )  # Classification of the error:
    # - User: Business logic or domain-level errors
    # - Deployment: Configuration, licensing, or permission issues
    # - System: Unexpected internal errors or infrastructure issues

    status: Optional[int] = (
        None  # HTTP status code, if relevant (e.g., when forwarded from a web API)
    )


class UiPathRuntimeStatus(str, Enum):
    """Standard status values for runtime execution."""

    SUCCESSFUL = "successful"
    FAULTED = "faulted"
    SUSPENDED = "suspended"


class UiPathRuntimeResult(BaseModel):
    """Result of an execution with status and optional error information."""

    output: Optional[Dict[str, Any]] = None
    status: UiPathRuntimeStatus = UiPathRuntimeStatus.SUCCESSFUL
    resume: Optional[UiPathResumeTrigger] = None
    error: Optional[UiPathErrorContract] = None

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


class UiPathRuntimeContext(BaseModel):
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
    result: Optional[UiPathRuntimeResult] = None

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


class UiPathRuntimeError(Exception):
    """Base exception class for UiPath runtime errors with structured error information."""

    def __init__(
        self,
        code: str,
        title: str,
        detail: str,
        category: UiPathErrorCategory = UiPathErrorCategory.UNKNOWN,
        status: Optional[int] = None,
        prefix: str = "Python",
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

        self.error_info = UiPathErrorContract(
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


class UiPathBaseRuntime(ABC):
    """
    Base runtime class implementing the async context manager protocol.
    This allows using the class with 'async with' statements.
    """

    def __init__(self, context: UiPathRuntimeContext):
        self.context = context

    @classmethod
    def from_context(cls, context: UiPathRuntimeContext):
        """
        Factory method to create a runtime instance from a context.

        Args:
            context: The runtime context with configuration

        Returns:
            An initialized Runtime instance
        """
        runtime = cls(context)
        return runtime

    async def __aenter__(self):
        """
        Async enter method called when entering the 'async with' block.
        Initializes and prepares the runtime environment.

        Returns:
            The runtime instance
        """
        # Intercept all stdout/stderr/logs and write them to a file (runtime), stdout (debug)
        self.logs_interceptor = LogsInterceptor(
            min_level=self.context.logs_min_level,
            dir=self.context.runtime_dir,
            file=self.context.logs_file,
            job_id=self.context.job_id,
        )
        self.logs_interceptor.setup()

        logger.debug(f"Starting runtime with job id: {self.context.job_id}")

        return self

    @abstractmethod
    async def execute(self) -> Optional[UiPathRuntimeResult]:
        """
        Execute with the provided context.

        Returns:
            Dictionary with execution results

        Raises:
            RuntimeError: If execution fails
        """
        pass

    @abstractmethod
    def validate(self):
        """Validate runtime inputs."""
        pass

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Async exit method called when exiting the 'async with' block.
        Cleans up resources and handles any exceptions.

        Always writes output file regardless of whether execution was successful,
        suspended, or encountered an error.
        """
        try:
            logger.debug(f"Shutting down runtime with job id: {self.context.job_id}")

            if self.context.result is None:
                execution_result = UiPathRuntimeResult()
            else:
                execution_result = self.context.result

            if exc_type:
                # Create error info from exception
                if isinstance(exc_val, UiPathRuntimeError):
                    error_info = exc_val.error_info
                else:
                    # Generic error
                    error_info = UiPathErrorContract(
                        code=f"ERROR_{exc_type.__name__}",
                        title=f"Runtime error: {exc_type.__name__}",
                        detail=str(exc_val),
                        category=UiPathErrorCategory.UNKNOWN,
                    )

                execution_result.status = UiPathRuntimeStatus.FAULTED
                execution_result.error = error_info

            content = execution_result.to_dict()
            logger.debug(content)

            # Always write output file at runtime
            if self.context.job_id:
                with open(self.output_file_path, "w") as f:
                    json.dump(content, f, indent=2, default=str)

            # Don't suppress exceptions
            return False

        except Exception as e:
            logger.error(f"Error during runtime shutdown: {str(e)}")

            # Create a fallback error result if we fail during cleanup
            if not isinstance(e, UiPathRuntimeError):
                error_info = UiPathErrorContract(
                    code="RUNTIME_SHUTDOWN_ERROR",
                    title="Runtime shutdown failed",
                    detail=f"Error: {str(e)}",
                    category=UiPathErrorCategory.SYSTEM,
                )
            else:
                error_info = e.error_info

            # Last-ditch effort to write error output
            try:
                error_result = UiPathRuntimeResult(
                    status=UiPathRuntimeStatus.FAULTED, error=error_info
                )
                error_result_content = error_result.to_dict()
                logger.debug(error_result_content)
                if self.context.job_id:
                    with open(self.output_file_path, "w") as f:
                        json.dump(error_result_content, f, indent=2, default=str)
            except Exception as write_error:
                logger.error(f"Failed to write error output file: {str(write_error)}")
                raise

            # Re-raise as RuntimeError if it's not already a UiPathRuntimeError
            if not isinstance(e, UiPathRuntimeError):
                raise RuntimeError(
                    error_info.code,
                    error_info.title,
                    error_info.detail,
                    error_info.category,
                ) from e
            raise
        finally:
            # Restore original logging
            if self.context.job_id and self.logs_interceptor:
                self.logs_interceptor.teardown()

    @cached_property
    def output_file_path(self) -> str:
        if self.context.runtime_dir and self.context.output_file:
            os.makedirs(self.context.runtime_dir, exist_ok=True)
            return os.path.join(self.context.runtime_dir, self.context.output_file)
        return os.path.join("__uipath", "output.json")

    @cached_property
    def state_file_path(self) -> str:
        if self.context.runtime_dir and self.context.state_file:
            os.makedirs(self.context.runtime_dir, exist_ok=True)
            return os.path.join(self.context.runtime_dir, self.context.state_file)
        return os.path.join("__uipath", "state.db")
