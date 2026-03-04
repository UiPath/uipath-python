"""Interrupt events for human-in-the-loop patterns."""

from enum import Enum
from typing import Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field


class InterruptTypeEnum(str, Enum):
    """Enum of known interrupt types."""

    TOOL_CALL_CONFIRMATION = "uipath_cas_tool_call_confirmation"


class UiPathConversationToolCallConfirmationValue(BaseModel):
    """Schema for tool call confirmation interrupt value."""

    tool_call_id: str = Field(..., alias="toolCallId")
    tool_name: str = Field(..., alias="toolName")
    input_schema: Any = Field(..., alias="inputSchema")
    input_value: Any | None = Field(None, alias="inputValue")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathConversationToolCallConfirmationInterruptStartEvent(BaseModel):
    """Tool call confirmation interrupt start event with strong typing."""

    type: Literal["uipath_cas_tool_call_confirmation"]
    value: UiPathConversationToolCallConfirmationValue

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathConversationGenericInterruptStartEvent(BaseModel):
    """Generic interrupt start event for custom interrupt types."""

    type: str
    value: Any

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


UiPathConversationInterruptStartEvent = Union[
    UiPathConversationToolCallConfirmationInterruptStartEvent,
    UiPathConversationGenericInterruptStartEvent,
]


class UiPathConversationToolCallConfirmationEndValue(BaseModel):
    """Schema for tool call confirmation end value."""

    approved: bool
    input: Any | None = None

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathConversationToolCallConfirmationInterruptEndEvent(BaseModel):
    """Tool call confirmation interrupt end event with strong typing."""

    type: Literal["uipath_cas_tool_call_confirmation"]
    value: UiPathConversationToolCallConfirmationEndValue

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathConversationGenericInterruptEndEvent(BaseModel):
    """Generic interrupt end event for custom interrupt types."""

    type: str
    value: Any

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


UiPathConversationInterruptEndEvent = Union[
    UiPathConversationToolCallConfirmationInterruptEndEvent,
    UiPathConversationGenericInterruptEndEvent,
]


class UiPathConversationInterruptEvent(BaseModel):
    """Encapsulates interrupt-related events within a message."""

    interrupt_id: str = Field(..., alias="interruptId")
    start: UiPathConversationInterruptStartEvent | None = Field(
        None, alias="startInterrupt"
    )
    end: UiPathConversationInterruptEndEvent | None = Field(None, alias="endInterrupt")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathConversationInterruptData(BaseModel):
    """Represents the core data of an interrupt within a message - a pause point where the agent needs external input."""

    type: str
    interrupt_value: Any = Field(..., alias="interruptValue")
    end_value: Any | None = Field(None, alias="endValue")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathConversationInterrupt(UiPathConversationInterruptData):
    """Represents an interrupt within a message - a pause point where the agent needs external input."""

    interrupt_id: str = Field(..., alias="interruptId")
    created_at: str = Field(..., alias="createdAt")
    updated_at: str = Field(..., alias="updatedAt")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)
