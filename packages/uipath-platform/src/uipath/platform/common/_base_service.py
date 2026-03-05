import inspect
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


class BaseService:
    def __init__(
        self, config: UiPathApiConfig, execution_context: UiPathExecutionContext
    ) -> None:
        self._logger = getLogger("uipath")
        self._config = config
        self._execution_context = execution_context

        self._url = UiPathUrl(self._config.base_url)

        default_client_kwargs = get_httpx_client_kwargs()

        client_kwargs = {
            **default_client_kwargs,  # SSL, proxy, timeout, redirects
            "base_url": self._url.base_url,
            "headers": Headers(self.default_headers),
        }

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

        try:
            stack = inspect.stack()

            # use the third frame because of the retry decorator
            caller_frame = stack[3].frame
            function_name = caller_frame.f_code.co_name

            if "self" in caller_frame.f_locals:
                module_name = type(caller_frame.f_locals["self"]).__name__
            elif "cls" in caller_frame.f_locals:
                module_name = caller_frame.f_locals["cls"].__name__
            else:
                module_name = ""
        except Exception:
            function_name = ""
            module_name = ""

        specific_component = (
            f"{module_name}.{function_name}" if module_name and function_name else ""
        )

        kwargs.setdefault("headers", {})
        kwargs["headers"][HEADER_USER_AGENT] = user_agent_value(specific_component)

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
        try:
            stack = inspect.stack()

            caller_frame = stack[4].frame
            function_name = caller_frame.f_code.co_name

            if "self" in caller_frame.f_locals:
                module_name = type(caller_frame.f_locals["self"]).__name__
            elif "cls" in caller_frame.f_locals:
                module_name = caller_frame.f_locals["cls"].__name__
            else:
                module_name = ""
        except Exception:
            function_name = ""
            module_name = ""

        specific_component = (
            f"{module_name}.{function_name}" if module_name and function_name else ""
        )

        return specific_component
