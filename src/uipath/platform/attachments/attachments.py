"""Module defining the attachment model for attachments."""

import uuid
from dataclasses import dataclass
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
    model_config = {
        "title": "UiPathAttachment",
    }


@dataclass
class BlobFileAccessInfo:
    """Information about blob file access for an attachment.

    Attributes:
        id: The unique identifier (UUID) of the attachment.
        uri: The blob storage URI for accessing the file.
        name: The name of the attachment file.
    """

    id: uuid.UUID
    uri: str
    name: str
