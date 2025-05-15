import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


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
        json_encoders={datetime: lambda v: v.isoformat() if v else None},
    )

    name: str = Field(alias="Name")
    creation_time: Optional[datetime] = Field(default=None, alias="CreationTime")
    last_modification_time: Optional[datetime] = Field(
        default=None, alias="LastModificationTime"
    )
    key: uuid.UUID = Field(alias="Key")
