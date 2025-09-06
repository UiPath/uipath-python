from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel

# ---------- Shared Types ----------

UiPathChatJSONValue = Union[str, int, float, bool, None, Dict[str, Any], List[Any]]
"""Represents any JSON-serializable value (string, number, boolean, null, object, or array)."""


# ---------- Citations ----------


class UiPathChatCitationSourceUrl(BaseModel):
    """Represents a citation source that is an external URL."""

    url: str
    title: Optional[str] = None


class UiPathChatCitationSourceMedia(BaseModel):
    """Represents a citation source that is a media object, such as a PDF document."""

    mime_type: str
    download_url: Optional[str] = None
    page_number: Optional[str] = None
    title: Optional[str] = None


UiPathChatCitationSource = Union[
    UiPathChatCitationSourceUrl,
    UiPathChatCitationSourceMedia,
]
"""Citation sources can be either a URL or a media reference."""


class UiPathChatCitation(BaseModel):
    """Represents a citation or reference to an external source within a content part."""

    citation_id: str
    offset: int
    length: int
    sources: List[UiPathChatCitationSource]


# ---------- Content Parts ----------


class UiPathChatContentPart(BaseModel):
    """Represents a part of a message's content, such as text, markdown, or an image."""

    content_part_id: Optional[str] = None
    mime_type: str
    data: str
    citations: Optional[List[UiPathChatCitation]] = None
    is_transcript: Optional[bool] = False
    is_incomplete: Optional[bool] = False


# ---------- Tool Calls ----------


class UiPathChatToolCallResult(BaseModel):
    """Represents the result of a tool call execution, including success values, errors, or cancellations."""

    timestamp: Optional[datetime] = None
    value: Optional[UiPathChatJSONValue] = None
    is_error: Optional[bool] = False
    cancelled: Optional[bool] = False


class UiPathChatToolCall(BaseModel):
    """Represents a call to an external tool or function within a message."""

    tool_call_id: str
    name: str
    arguments: Optional[Dict[str, Any]] = None
    timestamp: Optional[datetime] = None
    result: Optional[UiPathChatToolCallResult] = None


# ---------- Messages ----------


class UiPathChatMessageRole(str, Enum):
    """Identifies the role of the message sender."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class UiPathChatMessage(BaseModel):
    """Represents a single message in a conversation exchange."""

    message_id: str
    role: UiPathChatMessageRole
    content_parts: Optional[List[UiPathChatContentPart]] = None
    tool_calls: Optional[List[UiPathChatToolCall]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
