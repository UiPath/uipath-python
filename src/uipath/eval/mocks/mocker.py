"""Mocker definitions and implementations."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, TypeVar

T = TypeVar("T")
R = TypeVar("R")


class Mocker(ABC):
    """Mocker interface."""

    @abstractmethod
    async def response(
        self,
        func: Callable[[T], R],
        params: dict[str, Any],
        *args: T,
        **kwargs,
    ) -> R:
        """Respond with mocked response."""
        raise NotImplementedError()


class UiPathMockingNoMatcherError(Exception):
    """Exception when a mocker is unable to find a match with the invocation."""

    pass
