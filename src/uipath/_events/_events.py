import logging
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from opentelemetry.sdk.trace import ReadableSpan
from pydantic import BaseModel, ConfigDict, Field, model_validator

from uipath._cli._evals._models._evaluation_set import EvaluationItem
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
    no_of_evals: int
    evaluators: List[Any]


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

    MESSAGE_CREATED = "message_created"
    AGENT_STATE_UPDATED = "agent_state_updated"
    ERROR = "error"


class BaseEvent(BaseModel):
    """Base class for all UiPath events."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    event_type: EventType
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional event context"
    )


class MessageCreatedEvent(BaseEvent):
    """Event emitted when a message is created or streamed.

    Wraps framework-specific message objects (e.g., LangChain BaseMessage,
    CrewAI messages, AutoGen messages, etc.) without converting them.

    Attributes:
        payload: The framework-specific message object
        event_type: Automatically set to MESSAGE_CREATED
        metadata: Additional context (conversation_id, exchange_id, etc.)

    Example:
        # LangChain
        event = MessageCreatedEvent(
            payload=AIMessage(content="Hello"),
            metadata={"conversation_id": "123"}
        )

        # Access the message
        message = event.payload  # BaseMessage
        print(message.content)
    """

    payload: Any = Field(description="Framework-specific message object")
    event_type: EventType = Field(default=EventType.MESSAGE_CREATED, frozen=True)


class AgentStateUpdatedEvent(BaseEvent):
    """Event emitted when agent state is updated.

    Wraps framework-specific state update objects, preserving the original
    structure and data from the framework.

    Attributes:
        payload: The framework-specific state update (e.g., LangGraph state dict)
        node_name: Name of the node/agent that produced this update (if available)
        event_type: Automatically set to AGENT_STATE_UPDATED
        metadata: Additional context

    Example:
        # LangGraph
        event = AgentStateUpdatedEvent(
            payload={"messages": [...], "context": "..."},
            node_name="agent_node",
            metadata={"conversation_id": "123"}
        )

        # Access the state
        state = event.payload  # dict
        messages = state.get("messages", [])
    """

    payload: Dict[str, Any] = Field(description="Framework-specific state update")
    node_name: Optional[str] = Field(
        default=None, description="Name of the node/agent that caused this update"
    )
    event_type: EventType = Field(default=EventType.AGENT_STATE_UPDATED, frozen=True)
