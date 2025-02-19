from logging import getLogger
from typing import Any, Union

from httpx import (
    URL,
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

from uipath_sdk._utils._exceptions import (
    AuthenticationError,
    BadRequestError,
    ConflictError,
    NotFoundError,
    RateLimitError,
    UnprocessableEntityError,
)

from .._config import Config
from .._execution_context import ExecutionContext


def is_retryable_exception(exception: BaseException) -> bool:
    return isinstance(exception, (ConnectTimeout, TimeoutException))


def is_retryable_status_code(response: Response) -> bool:
    return response.status_code >= 500 and response.status_code < 600


class BaseService:
    def __init__(self, config: Config, execution_context: ExecutionContext) -> None:
        self._logger = getLogger("uipath")
        self._config = config
        self._execution_context = execution_context

        self._logger.debug(f"HEADERS: {self.default_headers}")
        self.client = Client(
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
        self._logger.debug(f"Request: {method} {url}")

        response = self.client.request(method, url, **kwargs)

        status_code = response.status_code
        if status_code in [400, 401, 404, 409, 422, 429]:
            if status_code == 400:
                raise BadRequestError()
            elif status_code == 401:
                raise AuthenticationError()
            elif status_code == 404:
                raise NotFoundError()
            elif status_code == 409:
                raise ConflictError()
            elif status_code == 422:
                raise UnprocessableEntityError()
            elif status_code == 429:
                raise RateLimitError()
        else:
            response.raise_for_status()

        return response

    @property
    def default_headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            **self.auth_headers,
            **self.custom_headers,
        }

    @property
    def auth_headers(self) -> dict[str, str]:
        header = f"Bearer {self._config.secret}"
        return {"Authorization": header}

    @property
    def custom_headers(self) -> dict[str, str]:
        return {}
