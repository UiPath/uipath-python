"""Custom exceptions for the UiPath SDK.

This module defines a hierarchy of custom exceptions used throughout the SDK
to provide more specific error handling and better error messages.
"""

from typing import Any, Optional


class UiPathError(Exception):
    """Base exception class for all UiPath SDK errors.

    All custom exceptions in the SDK should inherit from this class.

    Attributes:
            message: A human-readable error message
            details: Optional additional error details
    """

    def __init__(self, message: str, details: Optional[Any] = None) -> None:
        self.message = message
        self.details = details

        super().__init__(self.message)


class ConfigurationError(UiPathError):
    """Base class for configuration-related errors."""

    pass


class BaseUrlMissingError(ConfigurationError):
    """Raised when the base URL is not configured."""

    def __init__(
        self,
        message: str = "Authentication required. Please run \033[1muipath auth\033[22m.",
    ) -> None:
        super().__init__(message)


class AccessTokenMissingError(ConfigurationError):
    """Raised when the access token is not configured."""

    def __init__(
        self,
        message: str = "Authentication required. Please run \033[1muipath auth\033[22m.",
    ) -> None:
        super().__init__(message)


class APIError(UiPathError):
    """Base class for API-related errors.

    Attributes:
        status_code: The HTTP status code of the failed request
        response_body: The response body from the failed request
    """

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_body: Optional[str] = None,
    ) -> None:
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(
            message,
            details={"status_code": status_code, "response_body": response_body},
        )


class BadRequestError(APIError):
    """Raised when the API request is malformed (400)."""

    def __init__(self, response_body: str, message: str | None = None) -> None:
        if message is None:
            message = "Bad request"
        super().__init__(message, status_code=400, response_body=response_body)


class UnauthorizedError(APIError):
    """Raised when authentication fails (401)."""

    def __init__(self, response_body: str, message: str | None = None) -> None:
        if message is None:
            message = "Unauthorized"
        super().__init__(message, status_code=401, response_body=response_body)


class ForbiddenError(APIError):
    """Raised when the user doesn't have permission (403)."""

    def __init__(self, response_body: str, message: str | None = None) -> None:
        if message is None:
            message = "Forbidden"
        super().__init__(message, status_code=403, response_body=response_body)


class NotFoundError(APIError):
    """Raised when the requested resource is not found (404)."""

    def __init__(self, response_body: str, message: str | None = None) -> None:
        if message is None:
            message = "Not found"
        super().__init__(message, status_code=404, response_body=response_body)


class ConflictError(APIError):
    """Raised when the request cannot be processed due to a conflict (409)."""

    def __init__(self, response_body: str, message: str | None = None) -> None:
        if message is None:
            message = "Conflict"
        super().__init__(message, status_code=409, response_body=response_body)


class RateLimitError(APIError):
    """Raised when the API rate limit is exceeded (429)."""

    def __init__(self, response_body: str, message: str | None = None) -> None:
        if message is None:
            message = "Rate limit exceeded"
        super().__init__(message, status_code=429, response_body=response_body)


class ServerError(APIError):
    """Raised when the API server encounters an error (5xx)."""

    def __init__(self, response_body: str, message: str | None = None) -> None:
        if message is None:
            message = "Server error"
        super().__init__(message, status_code=500, response_body=response_body)
