from typing import List, Optional

from pydantic import BaseModel


class FieldDetails(BaseModel):
    name: str
    key: str


class ActionSchema(BaseModel):
    key: str
    inOuts: Optional[List[FieldDetails]] = None
    inputs: Optional[List[FieldDetails]] = None
    outputs: Optional[List[FieldDetails]] = None
    outcomes: Optional[List[FieldDetails]] = None
