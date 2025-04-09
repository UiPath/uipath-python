from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


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
        json_encoders={datetime: lambda v: v.isoformat() if v else None},
    )

    key: str
    in_outs: Optional[List[FieldDetails]] = Field(default=None, alias="inOuts")
    inputs: Optional[List[FieldDetails]] = None
    outputs: Optional[List[FieldDetails]] = None
    outcomes: Optional[List[FieldDetails]] = None
