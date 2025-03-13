from typing import Any, Union

from httpx import URL, Response

from .._config import Config
from .._execution_context import ExecutionContext
from .._folder_context import FolderContext
from ._base_service import BaseService


class ApiClient(FolderContext, BaseService):
    """Low-level client for making direct HTTP requests to the UiPath API.

    This class provides a flexible way to interact with the UiPath API when the
    higher-level service classes don't provide the needed functionality. It inherits
    from both FolderContext and BaseService to provide folder-aware request capabilities
    with automatic authentication and retry logic.
    """

    def __init__(self, config: Config, execution_context: ExecutionContext) -> None:
        super().__init__(config=config, execution_context=execution_context)

    def request(self, method: str, url: Union[URL, str], **kwargs: Any) -> Response:
        if kwargs.get("include_folder_headers", False):
            kwargs["headers"] = {
                **kwargs.get("headers", self.client.headers),
                **self.folder_headers,
            }

        if "include_folder_headers" in kwargs:
            del kwargs["include_folder_headers"]

        return super().request(method, url, **kwargs)
