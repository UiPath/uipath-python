import asyncio
import inspect
import random
import time
from datetime import datetime
from email.utils import parsedate_to_datetime
from logging import getLogger
from typing import Any, Literal, Union

from httpx import (
    URL,
    AsyncClient,
    Client,
    ConnectTimeout,
    Headers,
    HTTPStatusError,
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
from .._utils import UiPathUrl, user_agent_value
from .._utils._ssl_context import get_httpx_client_kwargs
from .._utils.constants import HEADER_USER_AGENT
from ..models.exceptions import EnrichedException


def is_retryable_exception(exception: BaseException) -> bool:
    return isinstance(exception, (ConnectTimeout, TimeoutException))


def is_retryable_status_code(response: Response) -> bool:
    return response.status_code >= 500 and response.status_code < 600


class BaseService:
    MAX_RETRIES = 3

    def __init__(self, config: Config, execution_context: ExecutionContext) -> None:
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

    def _parse_retry_after(self, headers: Headers) -> float:
        """Parse Retry-After header (RFC 6585/7231).

        Args:
            headers: HTTP response headers

        Returns:
            float: Seconds to wait before retry (minimum 0.0, default 1.0 if missing/invalid).
                  RFC 7231 allows 0 to indicate immediate retry.
        """
        DEFAULT_RETRY_AFTER = 1.0
        retry_after = headers.get("Retry-After")
        if not retry_after:
            return DEFAULT_RETRY_AFTER

        try:
            # Clamp to non-negative to prevent ValueError in time.sleep()
            return max(float(retry_after), 0.0)
        except ValueError:
            pass

        try:
            retry_date = parsedate_to_datetime(retry_after)
            delta = (retry_date - datetime.now(retry_date.tzinfo)).total_seconds()
            return max(delta, 0.0)  # Allow 0 per RFC 7231, but not negative
        except (ValueError, TypeError):
            return DEFAULT_RETRY_AFTER

    @retry(
        retry=(
            retry_if_exception(is_retryable_exception)
            | retry_if_result(is_retryable_status_code)
        ),
        wait=wait_exponential(multiplier=1, min=1, max=10),
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

        scoped_url = self._url.scope_url(str(url), scoped)

        for attempt in range(self.MAX_RETRIES + 1):
            response = self._client.request(method, scoped_url, **kwargs)

            if response.status_code == 429:
                if attempt < self.MAX_RETRIES:
                    retry_after = self._parse_retry_after(response.headers)
                    jitter = random.uniform(0, 0.1 * retry_after)
                    sleep_time = retry_after + jitter
                    self._logger.warning(
                        f"Rate limited (429). Retrying after {sleep_time:.2f}s "
                        f"(attempt {attempt + 1}/{self.MAX_RETRIES})"
                    )
                    response.close()
                    time.sleep(sleep_time)
                    continue
                break

            break

        try:
            response.raise_for_status()
        except HTTPStatusError as e:
            # include the http response in the error message
            response.close()
            raise EnrichedException(e) from e

        return response

    @retry(
        retry=(
            retry_if_exception(is_retryable_exception)
            | retry_if_result(is_retryable_status_code)
        ),
        wait=wait_exponential(multiplier=1, min=1, max=10),
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

        scoped_url = self._url.scope_url(str(url), scoped)

        for attempt in range(self.MAX_RETRIES + 1):
            response = await self._client_async.request(method, scoped_url, **kwargs)

            if response.status_code == 429:
                if attempt < self.MAX_RETRIES:
                    retry_after = self._parse_retry_after(response.headers)
                    jitter = random.uniform(0, 0.1 * retry_after)
                    sleep_time = retry_after + jitter
                    self._logger.warning(
                        f"Rate limited (429). Retrying after {sleep_time:.2f}s "
                        f"(attempt {attempt + 1}/{self.MAX_RETRIES})"
                    )
                    await response.aclose()  # Release connection before retry
                    await asyncio.sleep(sleep_time)
                    continue
                break

            break

        try:
            response.raise_for_status()
        except HTTPStatusError as e:
            # include the http response in the error message
            await response.aclose()
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
