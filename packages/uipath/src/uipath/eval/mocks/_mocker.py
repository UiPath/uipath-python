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
        invocation: tuple[tuple[Any, ...], dict[str, Any]],
    ) -> R:
        """Respond with mocked response."""
        raise NotImplementedError()


def format_exception_message(e: BaseException) -> str:
    """Format an exception for wrapped error messages, always naming its type.

    Timeout and cancellation exceptions (``asyncio.TimeoutError``,
    ``CancelledError``, httpx timeouts) often have an empty ``str``, which
    otherwise produces blank, undiagnosable error messages downstream.
    """
    message = str(e).strip()
    return f"{type(e).__name__}: {message}" if message else type(e).__name__


class UiPathNoMockFoundError(Exception):
    """Exception when a mocker is unable to find a match with the invocation. This is a signal to invoke the real function."""

    pass


class UiPathMockResponseGenerationError(Exception):
    """Exception when a mocker is configured unable to generate a response."""

    pass


class UiPathInputMockingError(Exception):
    """Exception when input mocking fails."""

    pass
