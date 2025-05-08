import contextlib

import httpx

from ..models.errors import (
    APIError,
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    RateLimitError,
    ServerError,
    UnauthorizedError,
)


@contextlib.contextmanager
def handle_errors():
    try:
        yield
    except httpx.HTTPStatusError as e:
        content_type = e.response.headers.get("content-type")
        is_json_response = content_type and content_type.startswith("application/json")

        if is_json_response:
            error_body = e.response.json()
        else:
            error_body = e.response.text

        status_code = e.response.status_code

        if type(error_body) is dict:
            message = error_body.get("message")
        else:
            message = None

        match status_code:
            case 400:
                raise BadRequestError(error_body, message=message) from e
            case 401:
                raise UnauthorizedError(error_body, message=message) from e
            case 403:
                raise ForbiddenError(error_body, message=message) from e
            case 404:
                raise NotFoundError(error_body, message=message) from e
            case 409:
                raise ConflictError(error_body, message=message) from e
            case 429:
                raise RateLimitError(error_body, message=message) from e
            case code if code >= 500:
                raise ServerError(error_body, message=message) from e
            case _:
                raise APIError(str(e), status_code, error_body) from e
    except httpx.TimeoutException as e:
        raise TimeoutError(str(e)) from e
