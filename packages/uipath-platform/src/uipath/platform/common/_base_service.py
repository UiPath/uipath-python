import sys
import types
from logging import getLogger
from typing import Any, Literal, Union

from httpx import (
    URL,
    AsyncClient,
    Client,
    Headers,
    HTTPStatusError,
    Response,
)
from opentelemetry import trace
from tenacity import (
    retry,
    retry_if_exception,
    retry_if_result,
    stop_after_attempt,
)

from ..errors import EnrichedException
from ._config import UiPathApiConfig
from ._execution_context import UiPathExecutionContext
from ._http_config import get_httpx_client_kwargs
from ._service_url_overrides import inject_routing_headers, resolve_service_url
from ._url import UiPathUrl
from ._user_agent import user_agent_value
from .constants import HEADER_USER_AGENT
from .retry import (
    MAX_RETRY_ATTEMPTS,
    is_retryable_platform_exception,
    is_retryable_response,
    platform_wait_strategy,
)

_THIS_FILE = __file__
_MAX_CALLER_FRAMES = 5


def _get_caller_component() -> str:
    try:
        current: types.FrameType | None = sys._getframe(1)
        for _ in range(_MAX_CALLER_FRAMES):
            if current is None:
                break
            code = current.f_code
            if code.co_filename == _THIS_FILE:
                current = current.f_back
                continue
            # Skip frames from third-party libraries (e.g. tenacity)
            if "site-packages" in code.co_filename:
                current = current.f_back
                continue
            qualname = code.co_qualname
            if "." in qualname:
                parts = qualname.rsplit(".", 2)
                return f"{parts[-2]}.{parts[-1]}"
            current = current.f_back
    except Exception:
        pass
    return ""


_TRACE_PARENT_HEADER = "x-uipath-traceparent-id"


def _inject_trace_context(headers: dict[str, str]) -> None:
    """Inject UiPath trace context header from the active OTEL span."""
    span = trace.get_current_span()
    ctx = span.get_span_context()
    if ctx.trace_id and ctx.span_id:
        trace_id = format(ctx.trace_id, "032x")
        span_id = format(ctx.span_id, "016x")
        headers[_TRACE_PARENT_HEADER] = f"00-{trace_id}-{span_id}-01"


class BaseService:
    def __init__(
        self, config: UiPathApiConfig, execution_context: UiPathExecutionContext
    ) -> None:
        self._logger = getLogger("uipath")
        self._config = config
        self._execution_context = execution_context

        self._url = UiPathUrl(self._config.base_url)

        client_kwargs = get_httpx_client_kwargs(headers=self.default_headers)
        client_kwargs["base_url"] = self._url.base_url
        client_kwargs["headers"] = Headers(client_kwargs.get("headers", {}))

        self._client = Client(**client_kwargs)
        self._client_async = AsyncClient(**client_kwargs)

        self._logger.debug(f"HEADERS: {self.default_headers}")

        super().__init__()

    @retry(
        retry=(
            retry_if_exception(is_retryable_platform_exception)
            | retry_if_result(is_retryable_response)
        ),
        wait=platform_wait_strategy,
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        reraise=True,
    )
    def request(
        self,
        method: str,
        url: Union[URL, str],
        *,
        scoped: Literal["org", "tenant"] = "tenant",
        **kwargs: Any,
    ) -> Response:
        self._logger.debug(f"Request: {method} {url}")
        self._logger.debug(f"HEADERS: {kwargs.get('headers', self._client.headers)}")

        specific_component = _get_caller_component()

        kwargs.setdefault("headers", {})
        kwargs["headers"][HEADER_USER_AGENT] = user_agent_value(specific_component)
        _inject_trace_context(kwargs["headers"])

        override = resolve_service_url(str(url))
        if override:
            scoped_url = override
            inject_routing_headers(kwargs["headers"])
        else:
            scoped_url = self._url.scope_url(str(url), scoped)

        response = self._client.request(method, scoped_url, **kwargs)

        try:
            response.raise_for_status()
        except HTTPStatusError as e:
            # include the http response in the error message
            raise EnrichedException(e) from e

        return response

    @retry(
        retry=(
            retry_if_exception(is_retryable_platform_exception)
            | retry_if_result(is_retryable_response)
        ),
        wait=platform_wait_strategy,
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        reraise=True,
    )
    async def request_async(
        self,
        method: str,
        url: Union[URL, str],
        *,
        scoped: Literal["org", "tenant"] = "tenant",
        **kwargs: Any,
    ) -> Response:
        self._logger.debug(f"Request: {method} {url}")
        self._logger.debug(
            f"HEADERS: {kwargs.get('headers', self._client_async.headers)}"
        )

        kwargs.setdefault("headers", {})
        kwargs["headers"][HEADER_USER_AGENT] = user_agent_value(
            self._specific_component
        )
        _inject_trace_context(kwargs["headers"])

        override = resolve_service_url(str(url))
        if override:
            scoped_url = override
            inject_routing_headers(kwargs["headers"])
        else:
            scoped_url = self._url.scope_url(str(url), scoped)

        response = await self._client_async.request(method, scoped_url, **kwargs)

        try:
            response.raise_for_status()
        except HTTPStatusError as e:
            # include the http response in the error message
            raise EnrichedException(e) from e
        return response

    @property
    def default_headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
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

    @property
    def _specific_component(self) -> str:
        return _get_caller_component()
