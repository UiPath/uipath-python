import inspect
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
from .._utils import user_agent_value
from .._utils.constants import HEADER_USER_AGENT


def is_retryable_exception(exception: BaseException) -> bool:
    return isinstance(exception, (ConnectTimeout, TimeoutException))


def is_retryable_status_code(response: Response) -> bool:
    return response.status_code >= 500 and response.status_code < 600


class BaseService:
    def __init__(self, config: Config, execution_context: ExecutionContext) -> None:
        self._logger = getLogger("uipath")
        self._config = config
        self._execution_context = execution_context
        self._tenant_scope_client = Client(
            base_url=self._config.base_url, headers=Headers(self.default_headers)
        )
        self._tenant_scope_client_async = AsyncClient(
            base_url=self._config.base_url, headers=Headers(self.default_headers)
        )
        org_scope_base_url = self.__get_org_scope_base_url()
        self._org_scope_client = Client(
            base_url=org_scope_base_url, headers=self.default_headers
        )
        self._org_scope_client_async = AsyncClient(
            base_url=org_scope_base_url, headers=self.default_headers
        )

        self._logger.debug(f"HEADERS: {self.default_headers}")

        super().__init__()

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
        **kwargs: Any,
    ) -> Response:
        self._logger.debug(f"Request: {method} {url}")
        self._logger.debug(
            f"HEADERS: {kwargs.get('headers', self._tenant_scope_client.headers)}"
        )

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
        headers = kwargs.get("headers", {})
        headers[HEADER_USER_AGENT] = user_agent_value(specific_component)

        response = self._tenant_scope_client.request(method, url, **kwargs)
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
        self,
        method: str,
        url: Union[URL, str],
        **kwargs: Any,
    ) -> Response:
        self._logger.debug(f"Request: {method} {url}")
        self._logger.debug(
            f"HEADERS: {kwargs.get('headers', self._tenant_scope_client.headers)}"
        )

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
        headers = kwargs.get("headers", {})
        headers[HEADER_USER_AGENT] = user_agent_value(specific_component)

        response = await self._tenant_scope_client_async.request(method, url, **kwargs)
        response.raise_for_status()

        return response

    def request_org_scope(
        self,
        method: str,
        url: Union[URL, str],
        **kwargs: Any,
    ) -> Response:
        self._logger.debug(f"Request: {method} {url}")
        self._logger.debug(
            f"HEADERS: {kwargs.get('headers', self._tenant_scope_client.headers)}"
        )

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
        headers = kwargs.get("headers", {})
        headers[HEADER_USER_AGENT] = user_agent_value(specific_component)

        response = self._org_scope_client.request(method, url, **kwargs)
        response.raise_for_status()

        return response

    async def request_org_scope_async(
        self,
        method: str,
        url: Union[URL, str],
        **kwargs: Any,
    ) -> Response:
        self._logger.debug(f"Request: {method} {url}")
        self._logger.debug(
            f"HEADERS: {kwargs.get('headers', self._tenant_scope_client.headers)}"
        )

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
        headers = kwargs.get("headers", {})
        headers[HEADER_USER_AGENT] = user_agent_value(specific_component)

        response = await self._org_scope_client_async.request(method, url, **kwargs)
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

    def __get_org_scope_base_url(self) -> str:
        base_url = str(self._config.base_url)
        if base_url.endswith("/"):
            base_url = base_url[:-1]
        return base_url.rsplit("/", 1)[0] + "/"
