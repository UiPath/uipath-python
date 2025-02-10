from logging import getLogger
from typing import Any, ParamSpec, TypedDict

from httpx import URL, Client, Headers, HTTPError, Response
from httpx._types import (
    CookieTypes,
    HeaderTypes,
    QueryParamTypes,
    RequestContent,
    RequestData,
    RequestFiles,
)

from .._config import Config
from .._execution_context import ExecutionContext
from .._utils.retry_decorator import retry

Param = ParamSpec("Param")


class RequestOptions(TypedDict, total=False):
    content: RequestContent | None
    data: RequestData | None
    files: RequestFiles | None
    json: Any | None
    params: QueryParamTypes | None
    headers: HeaderTypes | None
    cookies: CookieTypes | None


class BaseService:
    def __init__(self, config: Config, execution_context: ExecutionContext) -> None:
        self._logger = getLogger("uipath")
        self._config = config
        self._execution_context = execution_context

        self._logger.debug(f"HEADERS: {self.default_headers}")
        self.client = Client(
            base_url=self._config.base_url, headers=Headers(self.default_headers)
        )

    @retry(times=3, exceptions=(HTTPError,))
    def request(self, method: str, url: URL | str, **kwargs: Any) -> Response:
        self._logger.debug(f"Request: {method} {url}")
        return self.client.request(method, url, **kwargs)

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
        header = f"Basic {self._config.secret}"
        return {"Authorization": header}

    @property
    def custom_headers(self) -> dict[str, str]:
        return {}
