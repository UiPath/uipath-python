from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class NonPaginatedResponse(BaseModel, Generic[T]):
    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
    )
    items: List[T]
    total_count: Optional[int]


class PaginatedResponse(BaseModel, Generic[T]):
    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
    )

    items: List[T]
    total_count: Optional[int]
    has_next_page: Optional[bool]
    next_cursor: Optional[str]
    previous_cursor: Optional[str]
    current_page: Optional[int]
    total_pages: Optional[int]
