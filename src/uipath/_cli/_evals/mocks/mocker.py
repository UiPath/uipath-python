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


class UiPathNoMockFoundError(Exception):
    """Exception when a mocker is unable to find a match with the invocation. This is a signal to invoke the real function."""

    pass


class UiPathMockResponseGenerationError(Exception):
    """Exception when a mocker is configured unable to generate a response."""

    pass


class UiPathInputMockingError(Exception):
    """Exception when input mocking fails."""

    pass
