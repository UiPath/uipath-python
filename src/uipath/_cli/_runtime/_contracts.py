"""Core runtime contracts that define the interfaces between components."""

import json
import logging
import os
import sys
import traceback
from abc import ABC, abstractmethod
from enum import Enum
from functools import cached_property
from typing import (
    Any,
    AsyncGenerator,
    Callable,
    Dict,
    Generic,
    List,
    Literal,
    Optional,
    Type,
    TypeVar,
    Union,
)
from uuid import uuid4

from opentelemetry import context as context_api
from opentelemetry import trace
from opentelemetry.instrumentation.instrumentor import BaseInstrumentor  # type: ignore
from opentelemetry.sdk.trace import Span, SpanProcessor, TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SimpleSpanProcessor,
    SpanExporter,
)
from opentelemetry.trace import Tracer
from pydantic import BaseModel, Field

from uipath._events._events import UiPathRuntimeEvent
from uipath.agent.conversation import UiPathConversationEvent, UiPathConversationMessage
from uipath.tracing import TracingManager

from ..models.runtime_schema import Bindings, Entrypoint
from ._logging import LogsInterceptor

logger = logging.getLogger(__name__)

T = TypeVar("T", bound="UiPathBaseRuntime")
C = TypeVar("C", bound="UiPathRuntimeContext")


class UiPathResumeTriggerType(str, Enum):
    """Constants representing different types of resume job triggers in the system."""

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
    folder_path: Optional[str] = Field(default=None, alias="folderPath")
    folder_key: Optional[str] = Field(default=None, alias="folderKey")
    payload: Optional[Any] = Field(default=None, alias="interruptObject")

    model_config = {"populate_by_name": True}


class UiPathErrorCategory(str, Enum):
    """Categories of runtime errors."""

    DEPLOYMENT = "Deployment"  # Configuration, licensing, or permission issues
    SYSTEM = "System"  # Unexpected internal errors or infrastructure issues
    UNKNOWN = "Unknown"  # Default category when the error type is not specified
    USER = "User"  # Business logic or domain-level errors


class UiPathErrorCode(str, Enum):
    """Standard error codes for UiPath runtime errors."""

    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    # Entrypoint related errors
    ENTRYPOINT_MISSING = "ENTRYPOINT_MISSING"
    ENTRYPOINT_NOT_FOUND = "ENTRYPOINT_NOT_FOUND"
    ENTRYPOINT_FUNCTION_MISSING = "ENTRYPOINT_FUNCTION_MISSING"

    # Module and execution errors
    IMPORT_ERROR = "IMPORT_ERROR"
    MODULE_EXECUTION_ERROR = "MODULE_EXECUTION_ERROR"
    FUNCTION_EXECUTION_ERROR = "FUNCTION_EXECUTION_ERROR"
    EXECUTION_ERROR = "EXECUTION_ERROR"

    # Input validation errors
    INVALID_INPUT_FILE_EXTENSION = "INVALID_INPUT_FILE_EXTENSION"
    INPUT_INVALID_JSON = "INPUT_INVALID_JSON"

    # Process and job related errors
    INVOKED_PROCESS_FAILURE = "INVOKED_PROCESS_FAILURE"
    API_CONNECTION_ERROR = "API_CONNECTION_ERROR"

    # HITL (Human-In-The-Loop) related errors
    HITL_FEEDBACK_FAILURE = "HITL_FEEDBACK_FAILURE"
    UNKNOWN_HITL_MODEL = "UNKNOWN_HITL_MODEL"
    HITL_ACTION_CREATION_FAILED = "HITL_ACTION_CREATION_FAILED"

    # Trigger type errors
    UNKNOWN_TRIGGER_TYPE = "UNKNOWN_TRIGGER_TYPE"

    # Runtime shutdown errors
    RUNTIME_SHUTDOWN_ERROR = "RUNTIME_SHUTDOWN_ERROR"

    REFRESH_TOKEN_MISSING = "REFRESH_TOKEN_MISSING"


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
        output_data = self.output or {}
        if isinstance(self.output, BaseModel):
            output_data = self.output.model_dump()

        result = {
            "output": output_data,
            "status": self.status,
        }

        if self.resume:
            result["resume"] = self.resume.model_dump(by_alias=True)

        if self.error:
            result["error"] = self.error.model_dump()

        return result


class UiPathBreakpointResult(UiPathRuntimeResult):
    """Result for execution suspended at a breakpoint."""

    # Force status to always be SUSPENDED
    status: UiPathRuntimeStatus = Field(
        default=UiPathRuntimeStatus.SUSPENDED, frozen=True
    )
    breakpoint_node: str  # Which node the breakpoint is at
    breakpoint_type: Literal["before", "after"]  # Before or after the node
    current_state: dict[str, Any] | Any  # Current workflow state at breakpoint
    next_nodes: List[str]  # Which node(s) will execute next


class UiPathConversationHandler(ABC):
    """Base delegate for handling UiPath conversation events."""

    use_streaming: bool = True

    @abstractmethod
    def on_event(self, event: UiPathConversationEvent) -> None:
        """Handle a conversation event for a given execution run."""
        pass


class UiPathTraceContext(BaseModel):
    """Trace context information for tracing and debugging."""

    trace_id: Optional[str] = None
    parent_span_id: Optional[str] = None
    root_span_id: Optional[str] = None
    org_id: Optional[str] = None
    tenant_id: Optional[str] = None
    job_id: Optional[str] = None
    folder_key: Optional[str] = None
    process_key: Optional[str] = None
    enabled: Union[bool, str] = False
    reference_id: Optional[str] = None


class UiPathRuntimeContextBuilder:
    """Builder class for UiPathRuntimeContext following the builder pattern."""

    def __init__(self):
        self._kwargs = {}

    def with_defaults(
        self, config_path: Optional[str] = None, **kwargs
    ) -> "UiPathRuntimeContextBuilder":
        """Apply default configuration similar to UiPathRuntimeContext.with_defaults().

        Args:
            config_path: Path to the configuration file (defaults to UIPATH_CONFIG_PATH env var or "uipath.json")
            **kwargs: Additional keyword arguments to pass to with_defaults

        Returns:
            Self for method chaining
        """
        from os import environ as env

        resolved_config_path = config_path or env.get(
            "UIPATH_CONFIG_PATH", "uipath.json"
        )
        self._kwargs["config_path"] = resolved_config_path

        self._kwargs.update(
            {
                "job_id": env.get("UIPATH_JOB_KEY"),
                "trace_id": env.get("UIPATH_TRACE_ID"),
                "tracing_enabled": env.get("UIPATH_TRACING_ENABLED", True),
                "logs_min_level": env.get("LOG_LEVEL", "INFO"),
                **kwargs,  # Allow overriding defaults with provided kwargs
            }
        )

        self._kwargs["trace_context"] = UiPathTraceContext(
            trace_id=env.get("UIPATH_TRACE_ID"),
            parent_span_id=env.get("UIPATH_PARENT_SPAN_ID"),
            root_span_id=env.get("UIPATH_ROOT_SPAN_ID"),
            enabled=env.get("UIPATH_TRACING_ENABLED", True),
            job_id=env.get("UIPATH_JOB_KEY"),
            org_id=env.get("UIPATH_ORGANIZATION_ID"),
            tenant_id=env.get("UIPATH_TENANT_ID"),
            process_key=env.get("UIPATH_PROCESS_UUID"),
            folder_key=env.get("UIPATH_FOLDER_KEY"),
            reference_id=env.get("UIPATH_JOB_KEY") or str(uuid4()),
        )

        return self

    def with_entrypoint(self, entrypoint: str) -> "UiPathRuntimeContextBuilder":
        """Set the entrypoint for the runtime context.

        Args:
            entrypoint: The entrypoint to execute

        Returns:
            Self for method chaining
        """
        self._kwargs["entrypoint"] = entrypoint
        return self

    def with_input(
        self, input_data: Optional[str] = None, input_file: Optional[str] = None
    ) -> "UiPathRuntimeContextBuilder":
        """Set the input data for the runtime context.

        Args:
            input_data: The input data as a string
            input_file: Path to the input file

        Returns:
            Self for method chaining
        """
        if input_data is not None:
            self._kwargs["input"] = input_data
        if input_file is not None:
            self._kwargs["input_file"] = input_file
        return self

    def with_resume(self, enable: bool = True) -> "UiPathRuntimeContextBuilder":
        """Enable or disable resume mode for the runtime context.

        Args:
            enable: Whether to enable resume mode (defaults to True)

        Returns:
            Self for method chaining
        """
        self._kwargs["resume"] = enable
        return self

    def mark_eval_run(self, enable: bool = True) -> "UiPathRuntimeContextBuilder":
        """Mark this as an evaluation run.

        Args:
            enable: Whether this is an eval run (defaults to True)

        Returns:
            Self for method chaining
        """
        self._kwargs["is_eval_run"] = enable
        return self

    def build(self) -> "UiPathRuntimeContext":
        """Build and return the UiPathRuntimeContext instance.

        Returns:
            A configured UiPathRuntimeContext instance
        """
        config_path = self._kwargs.pop("config_path", None)
        if config_path:
            # Create context from config first, then update with any additional kwargs
            context = UiPathRuntimeContext.from_config(config_path)
            for key, value in self._kwargs.items():
                if hasattr(context, key):
                    setattr(context, key, value)
            return context
        else:
            return UiPathRuntimeContext(**self._kwargs)


class UiPathRuntimeContext(BaseModel):
    """Context information passed throughout the runtime execution."""

    entrypoint: Optional[str] = None
    input: Optional[str] = None
    input_json: Optional[Any] = None
    input_message: Optional[UiPathConversationMessage] = None
    job_id: Optional[str] = None
    execution_id: Optional[str] = None
    trace_id: Optional[str] = None
    trace_context: Optional[UiPathTraceContext] = None
    tracing_enabled: Union[bool, str] = False
    resume: bool = False
    debug: bool = False
    config_path: str = "uipath.json"
    runtime_dir: Optional[str] = "__uipath"
    logs_file: Optional[str] = "execution.log"
    logs_min_level: Optional[str] = "INFO"
    output_file: str = "output.json"
    state_file: str = "state.db"
    result: Optional[UiPathRuntimeResult] = None
    execution_output_file: Optional[str] = None
    input_file: Optional[str] = None
    trace_file: Optional[str] = None
    is_eval_run: bool = False
    log_handler: Optional[logging.Handler] = None
    chat_handler: Optional[UiPathConversationHandler] = None
    is_conversational: Optional[bool] = None
    breakpoints: Optional[List[str] | Literal["*"]] = None
    intercept_logs: bool = True

    model_config = {"arbitrary_types_allowed": True, "extra": "allow"}

    @classmethod
    def with_defaults(cls: type[C], config_path: Optional[str] = None, **kwargs) -> C:
        """Construct a context with defaults, reading env vars and config file."""
        resolved_config_path = config_path or os.environ.get(
            "UIPATH_CONFIG_PATH", "uipath.json"
        )

        base = cls.from_config(resolved_config_path)

        bool_map = {"true": True, "false": False}
        tracing_enabled = os.environ.get("UIPATH_TRACING_ENABLED", True)
        if isinstance(tracing_enabled, str) and tracing_enabled.lower() in bool_map:
            tracing_enabled = bool_map[tracing_enabled.lower()]

        # Apply defaults from env
        base.job_id = os.environ.get("UIPATH_JOB_KEY")
        base.trace_id = os.environ.get("UIPATH_TRACE_ID")
        base.tracing_enabled = tracing_enabled
        base.logs_min_level = os.environ.get("LOG_LEVEL", "INFO")

        base.trace_context = UiPathTraceContext(
            trace_id=os.environ.get("UIPATH_TRACE_ID"),
            parent_span_id=os.environ.get("UIPATH_PARENT_SPAN_ID"),
            root_span_id=os.environ.get("UIPATH_ROOT_SPAN_ID"),
            enabled=tracing_enabled,
            job_id=os.environ.get("UIPATH_JOB_KEY"),
            org_id=os.environ.get("UIPATH_ORGANIZATION_ID"),
            tenant_id=os.environ.get("UIPATH_TENANT_ID"),
            process_key=os.environ.get("UIPATH_PROCESS_UUID"),
            folder_key=os.environ.get("UIPATH_FOLDER_KEY"),
            reference_id=os.environ.get("UIPATH_JOB_KEY") or str(uuid4()),
        )

        # Override with kwargs
        for k, v in kwargs.items():
            setattr(base, k, v)

        return base

    @classmethod
    def from_config(cls: type[C], config_path: Optional[str] = None, **kwargs) -> C:
        """Load configuration from uipath.json file."""
        path = config_path or "uipath.json"
        config = {}

        if os.path.exists(path):
            with open(path, "r") as f:
                config = json.load(f)
        instance = cls()

        mapping = {
            "dir": "runtime_dir",
            "outputFile": "output_file",
            "stateFile": "state_file",
            "logsFile": "logs_file",
        }

        attributes_set = set()
        if "runtime" in config:
            runtime_config = config["runtime"]
            for config_key, attr_name in mapping.items():
                if config_key in runtime_config and hasattr(instance, attr_name):
                    attributes_set.add(attr_name)
                    setattr(instance, attr_name, runtime_config[config_key])

        for _, attr_name in mapping.items():
            if attr_name in kwargs and hasattr(instance, attr_name):
                if attr_name not in attributes_set:
                    setattr(instance, attr_name, kwargs[attr_name])
        return instance


class UiPathBaseRuntimeError(Exception):
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
                detail = f"{detail}\n\n{tb}"

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


class UiPathRuntimeError(UiPathBaseRuntimeError):
    """Exception class for UiPath runtime errors."""

    def __init__(
        self,
        code: UiPathErrorCode,
        title: str,
        detail: str,
        category: UiPathErrorCategory = UiPathErrorCategory.UNKNOWN,
        status: Optional[int] = None,
        prefix: str = "Python",
        include_traceback: bool = True,
    ):
        super().__init__(
            code=code.value,
            title=title,
            detail=detail,
            category=category,
            status=status,
            prefix=prefix,
            include_traceback=include_traceback,
        )


class UiPathRuntimeStreamNotSupportedError(NotImplementedError):
    """Raised when a runtime does not support streaming."""

    pass


class UiPathBaseRuntime(ABC):
    """Base runtime class implementing the async context manager protocol.

    This allows using the class with 'async with' statements.
    """

    def __init__(self, context: UiPathRuntimeContext):
        self.context = context

    @classmethod
    def from_context(cls, context: UiPathRuntimeContext):
        """Factory method to create a runtime instance from a context.

        Args:
            context: The runtime context with configuration

        Returns:
            An initialized Runtime instance
        """
        runtime = cls(context)
        return runtime

    async def get_bindings(self) -> Bindings:
        """Get binding resources for this runtime.

        Returns: A bindings object.
        """
        raise NotImplementedError()

    async def get_entrypoint(self) -> Entrypoint:
        """Get entrypoint for this runtime.

        Returns: A entrypoint for this runtime.
        """
        raise NotImplementedError()

    async def __aenter__(self):
        """Async enter method called when entering the 'async with' block.

        Initializes and prepares the runtime environment.

        Returns:
            The runtime instance
        """
        # Read the input from file if provided
        if self.context.input_file:
            _, file_extension = os.path.splitext(self.context.input_file)
            if file_extension != ".json":
                raise UiPathRuntimeError(
                    code=UiPathErrorCode.INVALID_INPUT_FILE_EXTENSION,
                    title="Invalid Input File Extension",
                    detail="The provided input file must be in JSON format.",
                )
            with open(self.context.input_file) as f:
                self.context.input = f.read()

        try:
            if self.context.input:
                self.context.input_json = json.loads(self.context.input)
            if self.context.input_json is None:
                self.context.input_json = {}
        except json.JSONDecodeError as e:
            raise UiPathRuntimeError(
                UiPathErrorCode.INPUT_INVALID_JSON,
                "Invalid JSON input",
                f"The input data is not valid JSON: {str(e)}",
                UiPathErrorCategory.USER,
            ) from e

        await self.validate()

        # Intercept all stdout/stderr/logs
        # write to file (runtime) or stdout (debug)
        if self.context.intercept_logs:
            self.logs_interceptor = LogsInterceptor(
                min_level=self.context.logs_min_level,
                dir=self.context.runtime_dir,
                file=self.context.logs_file,
                job_id=self.context.job_id,
                execution_id=self.context.execution_id,
                is_debug_run=self.is_debug_run(),
                log_handler=self.context.log_handler,
            )
            self.logs_interceptor.setup()

        logger.debug(f"Starting runtime with job id: {self.context.job_id}")

        return self

    @abstractmethod
    async def execute(self) -> Optional[UiPathRuntimeResult]:
        """Execute with the provided context.

        Returns:
            Dictionary with execution results

        Raises:
            RuntimeError: If execution fails
        """
        pass

    async def stream(
        self,
    ) -> AsyncGenerator[Union[UiPathRuntimeEvent, UiPathRuntimeResult], None]:
        """Stream execution events in real-time.

        This is an optional method that runtimes can implement to support streaming.
        If not implemented, only the execute() method will be available.

        Yields framework-agnostic BaseEvent instances during execution,
        with the final event being UiPathRuntimeResult.

        Yields:
            UiPathRuntimeEvent subclasses: Framework-agnostic events (UiPathAgentMessageEvent,
                                  UiPathAgentStateEvent, etc.)
            Final yield: UiPathRuntimeResult (or its subclass UiPathBreakpointResult)

        Raises:
            UiPathRuntimeStreamNotSupportedError: If the runtime doesn't support streaming
            RuntimeError: If execution fails

        Example:
            async for event in runtime.stream():
                if isinstance(event, UiPathRuntimeResult):
                    # Last event - execution complete
                    print(f"Status: {event.status}")
                    break
                elif isinstance(event, UiPathAgentMessageEvent):
                    # Handle message event
                    print(f"Message: {event.payload}")
                elif isinstance(event, UiPathAgentStateEvent):
                    # Handle state update
                    print(f"State updated by: {event.node_name}")
        """
        raise UiPathRuntimeStreamNotSupportedError(
            f"{self.__class__.__name__} does not implement streaming. "
            "Use execute() instead."
        )
        # This yield is unreachable but makes this a proper generator function
        # Without it, the function wouldn't match the AsyncGenerator return type
        yield

    @abstractmethod
    async def validate(self):
        """Validate runtime inputs."""
        pass

    @abstractmethod
    async def cleanup(self):
        """Cleaup runtime resources."""
        pass

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async exit method called when exiting the 'async with' block.

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

            # Always write output file at runtime, except evaluation runs
            if self.context.job_id and not self.context.is_eval_run:
                with open(self.output_file_path, "w") as f:
                    json.dump(content, f, indent=2, default=str)

            # Write the execution output to file if requested
            if self.context.execution_output_file:
                with open(self.context.execution_output_file, "w") as f:
                    if isinstance(execution_result.output, BaseModel):
                        f.write(execution_result.output.model_dump())
                    else:
                        json.dump(
                            execution_result.output or {}, f, indent=2, default=str
                        )

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
            if hasattr(self, "logs_interceptor"):
                self.logs_interceptor.teardown()

            await self.cleanup()

    def is_debug_run(self) -> bool:
        return not self.context.is_eval_run and not self.context.job_id

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


class UiPathRuntimeFactory(Generic[T, C]):
    """Generic factory for UiPath runtime classes."""

    def __init__(
        self,
        runtime_class: Type[T],
        context_class: Type[C],
        runtime_generator: Optional[Callable[[C], T]] = None,
        context_generator: Optional[Callable[..., C]] = None,
    ):
        if not issubclass(runtime_class, UiPathBaseRuntime):
            raise TypeError(
                f"runtime_class {runtime_class.__name__} must inherit from UiPathBaseRuntime"
            )

        if not issubclass(context_class, UiPathRuntimeContext):
            raise TypeError(
                f"context_class {context_class.__name__} must inherit from UiPathRuntimeContext"
            )

        self.runtime_class = runtime_class
        self.context_class = context_class
        self.runtime_generator = runtime_generator
        self.context_generator = context_generator
        self.tracer_provider: TracerProvider = TracerProvider()
        self.tracer_span_processors: List[SpanProcessor] = []
        self.logs_exporter: Optional[Any] = None
        trace.set_tracer_provider(self.tracer_provider)

    def add_span_exporter(
        self,
        span_exporter: SpanExporter,
        batch: bool = True,
    ) -> "UiPathRuntimeFactory[T, C]":
        """Add a span processor to the tracer provider."""
        span_processor: SpanProcessor
        if batch:
            span_processor = UiPathExecutionBatchTraceProcessor(span_exporter)
        else:
            span_processor = UiPathExecutionSimpleTraceProcessor(span_exporter)
        self.tracer_span_processors.append(span_processor)
        self.tracer_provider.add_span_processor(span_processor)
        return self

    def add_instrumentor(
        self,
        instrumentor_class: Type[BaseInstrumentor],
        get_current_span_func: Callable[[], Any],
    ) -> "UiPathRuntimeFactory[T, C]":
        """Add and instrument immediately."""
        instrumentor_class().instrument(tracer_provider=self.tracer_provider)
        TracingManager.register_current_span_provider(get_current_span_func)
        return self

    def new_context(self, **kwargs) -> C:
        """Create a new context instance."""
        if self.context_generator:
            return self.context_generator(**kwargs)
        return self.context_class(**kwargs)

    def new_runtime(self, **kwargs) -> T:
        """Create a new runtime instance."""
        context = self.new_context(**kwargs)
        if self.runtime_generator:
            return self.runtime_generator(context)
        return self.runtime_class.from_context(context)

    def from_context(self, context: C) -> T:
        """Create runtime instance from context."""
        if self.runtime_generator:
            return self.runtime_generator(context)
        return self.runtime_class.from_context(context)

    async def execute(self, context: C) -> Optional[UiPathRuntimeResult]:
        """Execute runtime with context."""
        async with self.from_context(context) as runtime:
            try:
                return await runtime.execute()
            finally:
                for span_processor in self.tracer_span_processors:
                    span_processor.force_flush()

    async def stream(
        self, context: C
    ) -> AsyncGenerator[Union[UiPathRuntimeEvent, UiPathRuntimeResult], None]:
        """Stream runtime execution with context.

        Args:
            context: The runtime context

        Yields:
            UiPathRuntimeEvent instances during execution and final UiPathRuntimeResult

        Raises:
            UiPathRuntimeStreamNotSupportedError: If the runtime doesn't support streaming
        """
        async with self.from_context(context) as runtime:
            try:
                async for event in runtime.stream():
                    yield event
            finally:
                for span_processor in self.tracer_span_processors:
                    span_processor.force_flush()

    async def execute_in_root_span(
        self,
        context: C,
        root_span: str = "root",
        attributes: Optional[dict[str, str]] = None,
    ) -> Optional[UiPathRuntimeResult]:
        """Execute runtime with context."""
        async with self.from_context(context) as runtime:
            try:
                tracer: Tracer = trace.get_tracer("uipath-runtime")
                span_attributes = {}
                if context.execution_id:
                    span_attributes["execution.id"] = context.execution_id
                if attributes:
                    span_attributes.update(attributes)

                with tracer.start_as_current_span(
                    root_span,
                    attributes=span_attributes,
                ):
                    return await runtime.execute()
            finally:
                for span_processor in self.tracer_span_processors:
                    span_processor.force_flush()

    async def stream_in_root_span(
        self,
        context: C,
        root_span: str = "root",
        attributes: Optional[dict[str, str]] = None,
    ) -> AsyncGenerator[Union[UiPathRuntimeEvent, UiPathRuntimeResult], None]:
        """Stream runtime execution with context in a root span.

        Args:
            context: The runtime context
            root_span: Name of the root span
            attributes: Optional attributes to add to the span

        Yields:
            UiPathRuntimeEvent instances during execution and final UiPathRuntimeResult

        Raises:
            UiPathRuntimeStreamNotSupportedError: If the runtime doesn't support streaming
        """
        async with self.from_context(context) as runtime:
            try:
                tracer: Tracer = trace.get_tracer("uipath-runtime")
                span_attributes = {}
                if context.execution_id:
                    span_attributes["execution.id"] = context.execution_id
                if attributes:
                    span_attributes.update(attributes)

                with tracer.start_as_current_span(
                    root_span,
                    attributes=span_attributes,
                ):
                    async for event in runtime.stream():
                        yield event
            finally:
                for span_processor in self.tracer_span_processors:
                    span_processor.force_flush()


class UiPathExecutionTraceProcessorMixin:
    def on_start(
        self, span: Span, parent_context: Optional[context_api.Context] = None
    ):
        """Called when a span is started."""
        if parent_context:
            parent_span = trace.get_current_span(parent_context)
        else:
            parent_span = trace.get_current_span()

        if parent_span and parent_span.is_recording():
            execution_id = parent_span.attributes.get("execution.id")  # type: ignore[attr-defined]
            if execution_id:
                span.set_attribute("execution.id", execution_id)
            evaluation_id = parent_span.attributes.get("evaluation.id")  # type: ignore[attr-defined]
            if evaluation_id:
                span.set_attribute("evaluation.id", evaluation_id)


class UiPathExecutionBatchTraceProcessor(
    UiPathExecutionTraceProcessorMixin, BatchSpanProcessor
):
    """Batch span processor that propagates execution.id."""


class UiPathExecutionSimpleTraceProcessor(
    UiPathExecutionTraceProcessorMixin, SimpleSpanProcessor
):
    """Simple span processor that propagates execution.id."""
