from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class GetResponse(BaseModel, Generic[T]):
    """Generic response for paginated GET requests."""

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    data: List[T] = Field(alias="data")
    cursor: Optional[str] = Field(default=None, alias="cursor")
