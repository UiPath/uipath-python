# mypy: disable-error-code="no-redef,arg-type"
import json
import logging
import os
import time
from typing import Any, Dict, List, Mapping, Optional

import httpx
import openai
from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import _cleanup_llm_representation
from pydantic import BaseModel, Field, SecretStr
from tenacity import (
    AsyncRetrying,
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from uipath_langchain._utils._settings import (
    UiPathClientFactorySettings,
    UiPathClientSettings,
    get_uipath_token_header,
)
from uipath_langchain._utils._sleep_policy import before_sleep_log


def get_from_uipath_url():
    url = os.getenv("UIPATH_URL")
    if url:
        return "/".join(url.split("/", 3)[:3])
    return None


class UiPathRequestMixin(BaseModel):
    class Config:
        arbitrary_types_allowed = True

    default_headers: Optional[Mapping[str, str]] = {
        "X-UiPath-Streaming-Enabled": "false",
    }
    model_name: Optional[str] = Field(
        default_factory=lambda: os.getenv("UIPATH_MODEL_NAME", "gpt-4o-2024-08-06"),
        alias="model",
    )
    settings: Optional[UiPathClientSettings] = None
    client_id: Optional[str] = Field(
        default_factory=lambda: os.getenv("UIPATH_CLIENT_ID")
    )
    client_secret: Optional[str] = Field(
        default_factory=lambda: os.getenv("UIPATH_CLIENT_SECRET")
    )
    base_url: Optional[str] = Field(
        default_factory=lambda data: getattr(data["settings"], "base_url", None)
        or os.getenv("UIPATH_BASE_URL")
        or get_from_uipath_url(),
        alias="azure_endpoint",
    )
    access_token: Optional[str] = Field(
        default_factory=lambda data: (
            getattr(data["settings"], "access_token", None)
            or os.getenv("UIPATH_ACCESS_TOKEN")  # Environment variable
            or os.getenv("UIPATH_SERVICE_TOKEN")  # Environment variable
            or get_uipath_token_header(
                UiPathClientFactorySettings(
                    UIPATH_BASE_URL=data["base_url"],
                    UIPATH_CLIENT_ID=data["client_id"],
                    UIPATH_CLIENT_SECRET=data["client_secret"],
                )
            )  # Get service token from UiPath
        )
    )
    org_id: Any = Field(
        default_factory=lambda data: getattr(data["settings"], "org_id", None)
        or os.getenv("UIPATH_ORGANIZATION_ID", "")
    )
    tenant_id: Any = Field(
        default_factory=lambda data: getattr(data["settings"], "tenant_id", None)
        or os.getenv("UIPATH_TENANT_ID", "")
    )
    requesting_product: Any = Field(
        default_factory=lambda data: getattr(
            data["settings"], "requesting_product", None
        )
        or os.getenv("UIPATH_REQUESTING_PRODUCT", "")
    )
    requesting_feature: Any = Field(
        default_factory=lambda data: getattr(
            data["settings"], "requesting_feature", None
        )
        or os.getenv("UIPATH_REQUESTING_FEATURE", "")
    )
    default_request_timeout: Any = Field(
        default_factory=lambda data: float(
            getattr(data["settings"], "timeout_seconds", None)
            or os.getenv("UIPATH_TIMEOUT_SECONDS", "120")
        ),
        alias="timeout",
    )

    openai_api_version: Optional[str] = Field(
        default_factory=lambda: os.getenv("OPENAI_API_VERSION", "2024-08-01-preview"),
        alias="api_version",
    )
    include_account_id: bool = False
    temperature: Optional[float] = 0.0
    max_tokens: Optional[int] = 1000
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None

    logger: Optional[logging.Logger] = None
    max_retries: Optional[int] = 5
    base_delay: float = 5.0
    max_delay: float = 60.0

    _url: Optional[str] = None
    _auth_headers: Optional[Dict[str, str]] = None

    # required to instantiate AzureChatOpenAI subclasses
    azure_endpoint: Optional[str] = Field(
        default="placeholder", description="Bypassed Azure endpoint"
    )
    openai_api_key: Optional[SecretStr] = Field(
        default=SecretStr("placeholder"), description="Bypassed API key"
    )
    # required to instatiate ChatAnthropic subclasses (will be needed when passthrough is implemented for Anthropic models)
    stop_sequences: Optional[List[str]] = Field(
        default=None, description="Bypassed stop sequence"
    )

    def _request(
        self, url: str, request_body: Dict[str, Any], headers: Dict[str, str]
    ) -> Dict[str, Any]:
        """Run an asynchronous call to the LLM."""
        # if self.logger:
        #     self.logger.info(f"Completion request: {request_body['messages'][:2]}")
        with httpx.Client(
            event_hooks={
                "request": [self._log_request_duration],
                "response": [self._log_response_duration],
            }
        ) as client:
            response = client.post(
                url,
                headers=headers,
                json=request_body,
                timeout=self.default_request_timeout,
            )

            # Handle HTTP errors and map them to OpenAI exceptions
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as err:
                if self.logger:
                    self.logger.error(
                        "Error querying UiPath: %s (%s)",
                        err.response.reason_phrase,
                        err.response.status_code,
                        extra={
                            "ActionName": self.settings.action_name,
                            "ActionId": self.settings.action_id,
                        }
                        if self.settings
                        else None,
                    )
                raise self._make_status_error_from_response(err.response) from err

            return response.json()

    def _call(
        self, url: str, request_body: Dict[str, Any], headers: Dict[str, str]
    ) -> Dict[str, Any]:
        """Run a synchronous call with retries to LLM"""
        if self.max_retries is None:
            return self._request(url, request_body, headers)

        retryer = Retrying(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential_jitter(
                initial=self.base_delay,
                max=self.max_delay,
                jitter=1.0,
            ),
            retry=retry_if_exception_type(
                (openai.RateLimitError, httpx.TimeoutException)
            ),
            reraise=True,
            before_sleep=before_sleep_log(self.logger, logging.WARNING)
            if self.logger is not None
            else None,
        )

        try:
            return retryer(self._request, url, request_body, headers)
        except openai.APIStatusError as err:
            if self.logger:
                self.logger.error(
                    "Failed querying LLM after retries: %s",
                    err,
                    extra={
                        "ActionName": self.settings.action_name,
                        "ActionId": self.settings.action_id,
                    }
                    if self.settings
                    else None,
                )
            raise err

    async def _arequest(
        self, url: str, request_body: Dict[str, Any], headers: Dict[str, str]
    ) -> Dict[str, Any]:
        # if self.logger:
        #     self.logger.info(f"Completion request: {request_body['messages'][:2]}")
        async with httpx.AsyncClient(
            event_hooks={
                "request": [self._alog_request_duration],
                "response": [self._alog_response_duration],
            }
        ) as client:
            response = await client.post(
                url,
                headers=headers,
                json=request_body,
                timeout=self.default_request_timeout,
            )
            # Handle HTTP errors and map them to OpenAI exceptions
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as err:
                if self.logger:
                    self.logger.error(
                        "Error querying LLM: %s (%s)",
                        err.response.reason_phrase,
                        err.response.status_code,
                        extra={
                            "ActionName": self.settings.action_name,
                            "ActionId": self.settings.action_id,
                        }
                        if self.settings
                        else None,
                    )
                raise self._make_status_error_from_response(err.response) from err

            return response.json()

    async def _acall(
        self, url: str, request_body: Dict[str, Any], headers: Dict[str, str]
    ) -> Dict[str, Any]:
        """Run an asynchronous call with retries to the LLM."""
        if self.max_retries is None:
            return await self._arequest(url, request_body, headers)

        retryer = AsyncRetrying(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential_jitter(
                initial=self.base_delay,
                max=self.max_delay,
                jitter=1.0,
            ),
            retry=retry_if_exception_type(
                (openai.RateLimitError, httpx.TimeoutException)
            ),
            reraise=True,
            before_sleep=before_sleep_log(self.logger, logging.WARNING)
            if self.logger is not None
            else None,
        )

        try:
            response: Any = await retryer(self._arequest, url, request_body, headers)
            if self.logger:
                self.logger.info(
                    f"[uipath_langchain_client] Finished retryer after {retryer.statistics['attempt_number'] - 1} retries",
                    extra={
                        "retry": f"{retryer.statistics['attempt_number'] - 1}",
                        "ActionName": self.settings.action_name,
                        "ActionId": self.settings.action_id,
                    }
                    if self.settings
                    else {
                        "retry": f"{retryer.statistics['attempt_number'] - 1}",
                    },
                )
            return response
        except openai.APIStatusError as err:
            if self.logger:
                self.logger.error(
                    "[uipath_langchain_client] Failed querying LLM after retries: %s",
                    err,
                    extra={
                        "reason": err.message,
                        "statusCode": err.status_code,
                        "ActionName": self.settings.action_name,
                        "ActionId": self.settings.action_id,
                    }
                    if self.settings
                    else {
                        "reason": err.message,
                        "statusCode": err.status_code,
                    },
                )
            raise err

    def _make_status_error_from_response(
        self,
        response: httpx.Response,
    ) -> openai.APIStatusError:
        """Function reproduced from openai._client to handle UiPath errors."""
        if response.is_closed and not response.is_stream_consumed:
            # We can't read the response body as it has been closed
            # before it was read. This can happen if an event hook
            # raises a status error.
            body = None
            err_msg = f"Error code: {response.status_code}"
        else:
            err_text = response.text.strip()
            body = err_text

            try:
                body = json.loads(err_text)
                err_msg = f"Error code: {response.status_code} - {body}"
            except Exception:
                err_msg = err_text or f"Error code: {response.status_code}"

        return self._make_status_error(err_msg, body=body, response=response)

    def _make_status_error(
        self,
        err_msg: str,
        *,
        body: object,
        response: httpx.Response,
    ) -> openai.APIStatusError:
        """Function reproduced from openai._client to handle UiPath errors."""
        data = body.get("error", body) if isinstance(body, Mapping) else body
        if response.status_code == 400:
            return openai.BadRequestError(err_msg, response=response, body=data)

        if response.status_code == 401:
            return openai.AuthenticationError(err_msg, response=response, body=data)

        if response.status_code == 403:
            return openai.PermissionDeniedError(err_msg, response=response, body=data)

        if response.status_code == 404:
            return openai.NotFoundError(err_msg, response=response, body=data)

        if response.status_code == 409:
            return openai.ConflictError(err_msg, response=response, body=data)

        if response.status_code == 422:
            return openai.UnprocessableEntityError(
                err_msg, response=response, body=data
            )

        if response.status_code == 429:
            return openai.RateLimitError(err_msg, response=response, body=data)

        if response.status_code >= 500:
            return openai.InternalServerError(err_msg, response=response, body=data)
        return openai.APIStatusError(err_msg, response=response, body=data)

    def _log_request_duration(self, request: httpx.Request):
        """Log the start time of the request."""
        if self.logger:
            request.extensions["start_time"] = time.monotonic()

    def _log_response_duration(self, response: httpx.Response):
        """Log the duration of the request."""
        if self.logger:
            start_time = response.request.extensions.get("start_time")
            if start_time:
                duration = time.monotonic() - start_time
                type = "embedding"
                if not isinstance(self, Embeddings):
                    type = "normalized" if self.is_normalized else "completion"
                self.logger.info(
                    f"[uipath_langchain_client] Request to {response.request.url} took {duration:.2f} seconds.",
                    extra={
                        "requestUrl": f"{response.request.url}",
                        "duration": f"{duration:.2f}",
                        "type": type,
                        "ActionName": self.settings.action_name,
                        "ActionId": self.settings.action_id,
                    }
                    if self.settings
                    else {
                        "requestUrl": f"{response.request.url}",
                        "duration": f"{duration:.2f}",
                        "type": type,
                    },
                )

    async def _alog_request_duration(self, request: httpx.Request):
        """Log the start time of the request."""
        self._log_request_duration(request)

    async def _alog_response_duration(self, response: httpx.Response):
        """Log the duration of the request."""
        self._log_response_duration(response)

    @property
    def _llm_type(self) -> str:
        """Get the type of language model used by this chat model. Used for logging purposes only."""
        return "uipath"

    @property
    def _identifying_params(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "model": self.model_name,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "frequency_penalty": self.frequency_penalty,
            "presence_penalty": self.presence_penalty,
        }

    def _prepare_url(self, url: str) -> httpx.URL:
        return httpx.URL(self.url)

    def _build_headers(self, options, retries_taken: int = 0) -> httpx.Headers:
        return httpx.Headers(self.auth_headers)

    @property
    def url(self) -> str:
        if not self._url:
            env_uipath_url = os.getenv("UIPATH_URL")

            if env_uipath_url:
                self._url = f"{env_uipath_url.rstrip('/')}/{self.endpoint}"
            else:
                self._url = (
                    f"{self.base_url}/{self.org_id}/{self.tenant_id}/{self.endpoint}"
                )
        return self._url

    @property
    def endpoint(self) -> str:
        raise NotImplementedError(
            "The endpoint property is not implemented for this class."
        )

    @property
    def auth_headers(self) -> Dict[str, str]:
        if not self._auth_headers:
            self._auth_headers = {
                **self.default_headers,  # type: ignore
                "Authorization": f"Bearer {self.access_token}",
                "X-UiPath-LlmGateway-RequestingProduct": self.requesting_product,
                "X-UiPath-LlmGateway-RequestingFeature": self.requesting_feature,
                "X-UiPath-LlmGateway-TimeoutSeconds": str(self.default_request_timeout),
            }
            if self.is_normalized and self.model_name:
                self._auth_headers["X-UiPath-LlmGateway-NormalizedApi-ModelName"] = (
                    self.model_name
                )
            if self.include_account_id:
                self._auth_headers["x-uipath-internal-accountid"] = self.org_id
                self._auth_headers["x-uipath-internal-tenantid"] = self.tenant_id
        return self._auth_headers

    def _get_llm_string(self, stop: Optional[list[str]] = None, **kwargs: Any) -> str:
        serialized_repr = getattr(self, "_serialized", self.model_dump())
        _cleanup_llm_representation(serialized_repr, 1)
        kwargs = serialized_repr.get("kwargs", serialized_repr)
        for key in [
            "base_url",
            "access_token",
            "client_id",
            "client_secret",
            "org_id",
            "tenant_id",
            "requesting_product",
            "requesting_feature",
            "azure_endpoint",
            "openai_api_version",
            "openai_api_key",
            "default_request_timeout",
            "max_retries",
            "base_delay",
            "max_delay",
            "logger",
            "settings",
        ]:
            if key in kwargs:
                kwargs.pop(key, None)
        llm_string = json.dumps(serialized_repr, sort_keys=True)
        return llm_string

    @property
    def is_normalized(self) -> bool:
        return False
