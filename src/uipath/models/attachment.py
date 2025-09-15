import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class Attachment(BaseModel):
    """Model representing an attachment in UiPath.

    Attachments can be associated with jobs in UiPath and contain binary files or documents.
    """

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
    )

    @field_serializer("creation_time", "last_modification_time", when_used="json")
    def serialize_datetime(self, value):
        if isinstance(value, datetime):
            return value.isoformat() if value else None
        return value

    name: str = Field(alias="Name")
    creation_time: Optional[datetime] = Field(default=None, alias="CreationTime")
    last_modification_time: Optional[datetime] = Field(
        default=None, alias="LastModificationTime"
    )
    key: uuid.UUID = Field(alias="Key")
