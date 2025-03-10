from logging import getLogger
from typing import Any, Union

from httpx import (
    URL,
    AsyncClient,
    Client,
    ConnectTimeout,
    Headers,
    Response,
    TimeoutException,
)
from tenacity import (
    retry,
    retry_if_exception,
    retry_if_result,
    wait_exponential,
)

from .._config import Config
from .._execution_context import ExecutionContext


def is_retryable_exception(exception: BaseException) -> bool:
    """
    Check if an exception should trigger a retry attempt.

    Args:
        exception (BaseException): The exception to check.

    Returns:
        bool: True if the exception is a connection or timeout error, False otherwise.
    """
    return isinstance(exception, (ConnectTimeout, TimeoutException))


def is_retryable_status_code(response: Response) -> bool:
    """
    Check if a response status code should trigger a retry attempt.

    Args:
        response (Response): The HTTP response to check.

    Returns:
        bool: True if the status code is in the 5xx range (server errors), False otherwise.
    """
    return response.status_code >= 500 and response.status_code < 600


class BaseService:
    """
    Base class for all UiPath API services.

    This class provides common functionality for making HTTP requests to the UiPath API,
    including authentication, retry logic, and header management. All specific service
    classes (AssetsService, ProcessesService, etc.) inherit from this base class.

    The class implements both synchronous and asynchronous request methods with automatic
    retry logic for handling transient failures and server errors.
    """

    def __init__(self, config: Config, execution_context: ExecutionContext) -> None:
        """
        Initialize a new service instance.

        Args:
            config (Config): Configuration object containing API settings like base URL and secret.
            execution_context (ExecutionContext): Context object containing execution-specific
                information like job ID and robot key.
        """
        self._logger = getLogger("uipath")
        self._config = config
        self._execution_context = execution_context

        self._logger.debug(f"HEADERS: {self.default_headers}")
        self.client = Client(
            base_url=self._config.base_url, headers=Headers(self.default_headers)
        )
        self.client_async = AsyncClient(
            base_url=self._config.base_url, headers=Headers(self.default_headers)
        )

        super().__init__()

    @retry(
        retry=(
            retry_if_exception(is_retryable_exception)
            | retry_if_result(is_retryable_status_code)
        ),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    def request(self, method: str, url: Union[URL, str], **kwargs: Any) -> Response:
        """
        Make a synchronous HTTP request to the UiPath API.

        This method automatically handles retries for transient failures and server errors
        using exponential backoff. It will retry on connection timeouts and 5xx status codes.

        Args:
            method (str): The HTTP method to use (GET, POST, PUT, DELETE, etc.).
            url (Union[URL, str]): The URL to send the request to.
            **kwargs (Any): Additional arguments to pass to the HTTP client.

        Returns:
            Response: The HTTP response from the API.

        Raises:
            HTTPStatusError: If the response indicates an HTTP error and max retries are exhausted.
            RequestError: If there's an error while making the request and max retries are exhausted.
        """
        self._logger.debug(f"Request: {method} {url}")
        self._logger.debug(f"HEADERS: {kwargs.get('headers', self.client.headers)}")

        response = self.client.request(method, url, **kwargs)

        response.raise_for_status()

        return response

    @retry(
        retry=(
            retry_if_exception(is_retryable_exception)
            | retry_if_result(is_retryable_status_code)
        ),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def request_async(
        self, method: str, url: Union[URL, str], **kwargs: Any
    ) -> Response:
        """
        Make an asynchronous HTTP request to the UiPath API.

        This method automatically handles retries for transient failures and server errors
        using exponential backoff. It will retry on connection timeouts and 5xx status codes.

        Args:
            method (str): The HTTP method to use (GET, POST, PUT, DELETE, etc.).
            url (Union[URL, str]): The URL to send the request to.
            **kwargs (Any): Additional arguments to pass to the HTTP client.

        Returns:
            Response: The HTTP response from the API.

        Raises:
            HTTPStatusError: If the response indicates an HTTP error and max retries are exhausted.
            RequestError: If there's an error while making the request and max retries are exhausted.
        """
        self._logger.debug(f"Request: {method} {url}")
        self._logger.debug(
            f"HEADERS: {kwargs.get('headers', self.client_async.headers)}"
        )

        response = await self.client_async.request(method, url, **kwargs)

        response.raise_for_status()

        return response

    @property
    def default_headers(self) -> dict[str, str]:
        """
        Get the default headers used for all API requests.

        These headers include:
        - Accept and Content-Type headers for JSON
        - Authentication headers
        - Any custom headers defined by the service

        Returns:
            dict[str, str]: A dictionary of default headers.
        """
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            **self.auth_headers,
            **self.custom_headers,
        }

    @property
    def auth_headers(self) -> dict[str, str]:
        """
        Get the authentication headers for API requests.

        Returns:
            dict[str, str]: A dictionary containing the Bearer token authorization header.
        """
        header = f"Bearer {self._config.secret}"
        return {"Authorization": header}

    @property
    def custom_headers(self) -> dict[str, str]:
        """
        Get custom headers for API requests.

        This method can be overridden by service classes to add their own headers.

        Returns:
            dict[str, str]: A dictionary of custom headers. Empty by default.
        """
        return {}
