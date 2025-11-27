"""Pagination result types for UiPath SDK."""

from dataclasses import dataclass
from typing import Generic, Iterator, List, Optional, TypeVar

__all__ = ["PagedResult"]

T = TypeVar("T")


@dataclass(frozen=True)
class PagedResult(Generic[T]):
    """Container for a single page of results from a paginated API.

    Attributes:
        items: The list of items in this page
        continuation_token: Token to fetch next page (REST APIs)
        has_more: Whether more results likely exist (OData APIs)
        skip: Number of items skipped (OData APIs)
        top: Maximum items requested (OData APIs)

    Example:
        # Offset-based pagination (OData)
        skip = 0
        while True:
            result = sdk.buckets.list(skip=skip, top=100)
            for bucket in result.items:
                process(bucket)
            if not result.has_more:
                break
            skip += 100

        # Cursor-based pagination (REST)
        token = None
        while True:
            result = sdk.buckets.list_files(
                name="my-storage",
                continuation_token=token
            )
            for file in result.items:
                process(file)
            if not result.continuation_token:
                break
            token = result.continuation_token
    """

    items: List[T]
    continuation_token: Optional[str] = None
    has_more: Optional[bool] = None
    skip: Optional[int] = None
    top: Optional[int] = None

    def __iter__(self) -> Iterator[T]:
        """Allow iteration over items directly."""
        return iter(self.items)

    def __len__(self) -> int:
        """Return the number of items in this page."""
        return len(self.items)

    def __bool__(self) -> bool:
        """Return True if page contains items."""
        return bool(self.items)
