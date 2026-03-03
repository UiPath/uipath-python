"""Common error event models used across all conversation event types."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class UiPathConversationErrorStartEvent(BaseModel):
    """Represents the start of an error condition."""

    message: str
    details: Any | None = None

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathConversationErrorEndEvent(BaseModel):
    """Represents the end of an error condition."""

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class UiPathConversationErrorEvent(BaseModel):
    """Encapsulates sub-events that represent the start and end of an error condition.

    This is a common error event model used across all event types (conversation, exchange,
    message, content part, citation, tool call, async input stream).
    """

    error_id: str = Field(..., alias="errorId")
    start: UiPathConversationErrorStartEvent | None = Field(None, alias="startError")
    end: UiPathConversationErrorEndEvent | None = Field(None, alias="endError")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)
