from typing import Any, ParamSpec, TypedDict

from httpx import URL, Client, HTTPError, Response
from httpx._types import (
    CookieTypes,
    HeaderTypes,
    QueryParamTypes,
    RequestContent,
    RequestData,
    RequestFiles,
)

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
    def __init__(self, client: Client) -> None:
        self.client = client

    @retry(times=3, exceptions=(HTTPError,))
    def request(self, method: str, url: URL | str, **kwargs: Any) -> Response:
        return self.client.request(method, url, **kwargs)
