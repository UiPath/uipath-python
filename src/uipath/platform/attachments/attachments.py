"""Module defining the attachment model for attachments."""

import uuid

from pydantic import BaseModel, Field


class Attachment(BaseModel):
    """Model representing an attachment."""

    id: uuid.UUID = Field(..., alias="ID")
    full_name: str = Field(..., alias="FullName")
    mime_type: str = Field(..., alias="MimeType")
