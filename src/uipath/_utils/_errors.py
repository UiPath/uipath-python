import json
from contextlib import contextmanager
from typing import Generator

import httpx

from ..models.errors import (
    APIError,
    UiPathError,
)


@contextmanager
def handle_errors() -> Generator[None, None, None]:
    """Context manager for handling HTTP and general errors in API calls.

    This context manager wraps API calls and converts various types of errors
    into appropriate UiPathError subclasses. It handles both HTTP errors
    and general exceptions.

    Yields:
        None: The context manager yields control to the wrapped code.

    Raises:
        APIError: For HTTP errors with status codes and error messages.
        UiPathError: For general exceptions that occur during API calls.
    """
    try:
        yield
    except httpx.HTTPStatusError as e:
        try:
            error_body = e.response.json()
        except Exception:
            error_body = e.response.text

        status_code = e.response.status_code

        message: str | None = None
        if isinstance(error_body, dict):
            message = (
                error_body.get("message")
                or error_body.get("error")
                or error_body.get("detail")
            )
            error_body = json.dumps(error_body)

        raise APIError(message or str(e), status_code, error_body) from e
    except Exception as e:
        breakpoint()
        raise UiPathError(str(e)) from e
