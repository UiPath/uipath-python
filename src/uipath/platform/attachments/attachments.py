"""Module defining the attachment model for attachments."""

import uuid
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class AttachmentMode(str, Enum):
    """Mode of attachment open."""

    READ = "read"
    WRITE = "write"


class Attachment(BaseModel):
    """Model representing an attachment. Id 'None' is used for uploads."""

    id: Optional[uuid.UUID] = Field(None, alias="ID")
    full_name: str = Field(..., alias="FullName")
    mime_type: str = Field(..., alias="MimeType")
