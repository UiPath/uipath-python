from typing import Any, Union

from httpx import URL, Response

from .._config import Config
from .._execution_context import ExecutionContext
from .._folder_context import FolderContext
from ._base_service import BaseService


class ApiClient(FolderContext, BaseService):
    """
    Low-level client for making direct HTTP requests to the UiPath API.

    This class provides a flexible way to interact with the UiPath API when the
    higher-level service classes don't provide the needed functionality. It inherits
    from both FolderContext and BaseService to provide folder-aware request capabilities
    with automatic authentication and retry logic.
    """

    def __init__(self, config: Config, execution_context: ExecutionContext) -> None:
        super().__init__(config=config, execution_context=execution_context)

    def request(self, method: str, url: Union[URL, str], **kwargs: Any) -> Response:
        """
        Make a direct HTTP request to the UiPath API.

        This method extends the base request method to optionally include folder headers
        when needed. It provides more flexibility than the higher-level service methods
        while still maintaining authentication and retry capabilities.

        Args:
            method (str): The HTTP method to use (GET, POST, PUT, DELETE, etc.).
            url (Union[URL, str]): The URL to send the request to.
            **kwargs (Any): Additional arguments to pass to the HTTP client.
                Special kwargs:
                - include_folder_headers (bool): If True, includes folder context headers
                  in the request. Defaults to False.

        Returns:
            Response: The HTTP response from the API.

        Example:
            ```python
            # Make a GET request with folder headers
            response = api_client.request(
                "GET",
                "/api/endpoint",
                include_folder_headers=True
            )
            ```
        """
        if kwargs.get("include_folder_headers", False):
            kwargs["headers"] = {
                **kwargs.get("headers", self.client.headers),
                **self.folder_headers,
            }

        if "include_folder_headers" in kwargs:
            del kwargs["include_folder_headers"]

        return super().request(method, url, **kwargs)

    async def request_async(
        self, method: str, url: Union[URL, str], **kwargs: Any
    ) -> Response:
        """
        Make an asynchronous HTTP request to the UiPath API.

        This method extends the base request method to optionally include folder headers
        when needed. It provides more flexibility than the higher-level service methods
        while still maintaining authentication and retry capabilities.

        Args:
            method (str): The HTTP method to use (GET, POST, PUT, DELETE, etc.).
            url (Union[URL, str]): The URL to send the request to.
            **kwargs (Any): Additional arguments to pass to the HTTP client.
                Special kwargs:
                - include_folder_headers (bool): If True, includes folder context headers

        Returns:
            Response: The HTTP response from the API.
        """
        if kwargs.get("include_folder_headers", False):
            kwargs["headers"] = {
                **kwargs.get("headers", self.client_async.headers),
                **self.folder_headers,
            }

        return await super().request_async(method, url, **kwargs)
