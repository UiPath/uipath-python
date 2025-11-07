import logging
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from opentelemetry.sdk.trace import ReadableSpan
from pydantic import BaseModel, ConfigDict, Field, SkipValidation, model_validator

from uipath._cli._evals._models._evaluation_set import EvaluationItem
from uipath.eval.evaluators import BaseEvaluator
from uipath.eval.models import EvalItemResult


class EvaluationEvents(str, Enum):
    CREATE_EVAL_SET_RUN = "create_eval_set_run"
    CREATE_EVAL_RUN = "create_eval_run"
    UPDATE_EVAL_SET_RUN = "update_eval_set_run"
    UPDATE_EVAL_RUN = "update_eval_run"


class EvalSetRunCreatedEvent(BaseModel):
    execution_id: str
    entrypoint: str
    eval_set_id: str
    eval_set_run_id: Optional[str] = None
    no_of_evals: int
    # skip validation to avoid abstract class instantiation
    evaluators: SkipValidation[List[BaseEvaluator[Any, Any, Any]]]


class EvalRunCreatedEvent(BaseModel):
    execution_id: str
    eval_item: EvaluationItem


class EvalItemExceptionDetails(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    runtime_exception: bool = False
    exception: Exception


class EvalRunUpdatedEvent(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    execution_id: str
    eval_item: EvaluationItem
    eval_results: List[EvalItemResult]
    success: bool
    agent_output: Any
    agent_execution_time: float
    spans: List[ReadableSpan]
    logs: List[logging.LogRecord]
    exception_details: Optional[EvalItemExceptionDetails] = None

    @model_validator(mode="after")
    def validate_exception_details(self):
        if not self.success and self.exception_details is None:
            raise ValueError("exception_details must be provided when success is False")
        return self


class EvalSetRunUpdatedEvent(BaseModel):
    execution_id: str
    evaluator_scores: dict[str, float]


ProgressEvent = Union[
    EvalSetRunCreatedEvent,
    EvalRunCreatedEvent,
    EvalRunUpdatedEvent,
    EvalSetRunUpdatedEvent,
]


class EventType(str, Enum):
    """Types of events that can be emitted during execution."""

    AGENT_MESSAGE = "agent_message"
    AGENT_STATE = "agent_state"
    ERROR = "error"


class UiPathRuntimeEvent(BaseModel):
    """Base class for all UiPath runtime events."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    event_type: EventType
    execution_id: Optional[str] = Field(
        default=None, description="The runtime execution id associated with the event"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional event context"
    )


class UiPathAgentMessageEvent(UiPathRuntimeEvent):
    """Event emitted when a message is created or streamed.

    Wraps framework-specific message objects (e.g., LangChain BaseMessage,
    CrewAI messages, AutoGen messages, etc.) without converting them.

    Attributes:
        payload: The framework-specific message object
        event_type: Automatically set to AGENT_MESSAGE
        metadata: Additional context

    Example:
        # LangChain
        event = UiPathAgentMessageEvent(
            payload=AIMessage(content="Hello"),
            metadata={"additional_prop": "123"}
        )

        # Access the message
        message = event.payload  # BaseMessage
        print(message.content)
    """

    payload: Any = Field(description="Framework-specific message object")
    event_type: EventType = Field(default=EventType.AGENT_MESSAGE, frozen=True)


class UiPathAgentStateEvent(UiPathRuntimeEvent):
    """Event emitted when agent state is updated.

    Wraps framework-specific state update objects, preserving the original
    structure and data from the framework.

    Attributes:
        payload: The framework-specific state update (e.g., LangGraph state dict)
        node_name: Name of the node/agent that produced this update (if available)
        event_type: Automatically set to AGENT_STATE
        metadata: Additional context

    Example:
        # LangGraph
        event = UiPathAgentStateEvent(
            payload={"messages": [...], "context": "..."},
            node_name="agent_node",
            metadata={"additional_prop": "123"}
        )

        # Access the state
        state = event.payload  # dict
        messages = state.get("messages", [])
    """

    payload: Dict[str, Any] = Field(description="Framework-specific state update")
    node_name: Optional[str] = Field(
        default=None, description="Name of the node/agent that caused this update"
    )
    event_type: EventType = Field(default=EventType.AGENT_STATE, frozen=True)
