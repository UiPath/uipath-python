from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class FieldDetails(BaseModel):
    name: str
    key: str


class ActionSchema(BaseModel):
    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
    )

    @field_serializer("*", when_used="json")
    def serialize_datetime(self, value):
        if isinstance(value, datetime):
            return value.isoformat() if value else None
        return value

    key: str
    in_outs: Optional[List[FieldDetails]] = Field(default=None, alias="inOuts")
    inputs: Optional[List[FieldDetails]] = None
    outputs: Optional[List[FieldDetails]] = None
    outcomes: Optional[List[FieldDetails]] = None
