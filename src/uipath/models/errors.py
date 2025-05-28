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
