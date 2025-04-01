import os
from typing import List, Optional

import httpx
from langchain_community.callbacks.manager import openai_callback_var
from langchain_openai.embeddings import AzureOpenAIEmbeddings, OpenAIEmbeddings
from pydantic import Field

from uipath_langchain._utils._request_mixin import UiPathRequestMixin
from uipath_langchain._utils._settings import UiPathEndpoints


class UiPathAzureOpenAIEmbeddings(UiPathRequestMixin, AzureOpenAIEmbeddings):
    """Custom Embeddings connector for LangChain integration with UiPath, with minimal changes compared to AzureOpenAIEmbeddings."""

    model_name: Optional[str] = Field(
        default_factory=lambda: os.getenv(
            "UIPATH_MODEL_NAME", "text-embedding-3-large"
        ),
        alias="model",
    )

    def __init__(self, **kwargs):
        super().__init__(
            http_client=httpx.Client(
                event_hooks={
                    "request": [self._log_request_duration],
                    "response": [self._log_response_duration],
                }
            ),
            http_async_client=httpx.AsyncClient(
                event_hooks={
                    "request": [self._alog_request_duration],
                    "response": [self._alog_response_duration],
                }
            ),
            **kwargs,
        )
        self.client._client._prepare_url = self._prepare_url
        self.client._client._build_headers = self._build_headers
        self.async_client._client._prepare_url = self._prepare_url
        self.async_client._client._build_headers = self._build_headers

    @property
    def endpoint(self) -> str:
        return UiPathEndpoints.EMBEDDING_ENDPOINT.value.format(
            model=self.model_name, api_version=self.openai_api_version
        )


class UiPathOpenAIEmbeddings(UiPathRequestMixin, OpenAIEmbeddings):
    """Custom Embeddings connector for LangChain integration with UiPath, with full control over the embedding call."""

    model_name: Optional[str] = Field(
        default_factory=lambda: os.getenv(
            "UIPATH_MODEL_NAME", "text-embedding-3-large"
        ),
        alias="model",
    )

    def embed_documents(
        self, texts: List[str], chunk_size: Optional[int] = None
    ) -> List[List[float]]:
        """Embed a list of documents using the UiPath."""
        embeddings = []
        total_tokens = 0
        # Process in chunks if specified
        chunk_size_ = chunk_size or self.chunk_size or len(texts)
        for i in range(0, len(texts), chunk_size_):
            chunk = texts[i : i + chunk_size_]
            payload = {"input": chunk}
            response = self._call(self.url, payload, self.auth_headers)
            chunk_embeddings = [r["embedding"] for r in response["data"]]
            total_tokens += response["usage"]["prompt_tokens"]
            embeddings.extend(chunk_embeddings)
        if contextvar := openai_callback_var.get():
            contextvar.prompt_tokens += total_tokens
            contextvar.total_tokens += total_tokens
            contextvar.successful_requests += 1
        return embeddings

    async def aembed_documents(
        self,
        texts: List[str],
        chunk_size: Optional[int] = None,
    ) -> List[List[float]]:
        """Async version of embed_documents."""
        embeddings = []
        total_tokens = 0
        # Process in chunks if specified
        chunk_size_ = chunk_size or self.chunk_size or len(texts)
        for i in range(0, len(texts), chunk_size_):
            chunk = texts[i : i + chunk_size_]
            payload = {"input": chunk}
            response = await self._acall(self.url, payload, self.auth_headers)
            chunk_embeddings = [r["embedding"] for r in response["data"]]
            total_tokens += response["usage"]["prompt_tokens"]
            embeddings.extend(chunk_embeddings)
        if contextvar := openai_callback_var.get():
            contextvar.prompt_tokens += total_tokens
            contextvar.total_tokens += total_tokens
            contextvar.successful_requests += 1
        return embeddings

    @property
    def endpoint(self) -> str:
        return UiPathEndpoints.EMBEDDING_ENDPOINT.value.format(
            model=self.model_name, api_version=self.openai_api_version
        )
