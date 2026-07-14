"""Transport foundation for the IXP design-time API.

All IXP design-time endpoints live under ``du_/api/designtimeapi`` and share a
small set of transport conventions that differ from the rest of the platform
SDK. This module centralises them in :class:`IxpDesigntimeService`, the base
class every IXP service (projects, taxonomy, labellings, documents, models)
builds on:

* **Base path** — every request is prefixed with ``du_/api/designtimeapi`` and
  scoped to ``{org}/{tenant}`` by :class:`BaseService`.
* **Mandatory api-version** — the gateway requires an explicit
  ``api-version=1.0`` query parameter on *every* call.
* **Strict path encoding** — dynamic path segments (project name, field name,
  tag, ...) may contain reserved characters, so each is percent-encoded with
  ``quote(safe="")`` (``/`` -> ``%2F``, space -> ``%20``).
* **No retry on writes** — unlike the platform default, non-idempotent verbs
  (POST/PUT/PATCH, including multipart upload) and DELETE are **not** retried,
  matching the CLI SDK's zero-retry contract so a transient 5xx cannot
  double-create or double-confirm. Only idempotent GETs keep the platform
  retry policy.
* **Multipart upload / binary download** — helpers for the ``file`` multipart
  field and for reading raw bytes + content-type back.

Errors surface as :class:`~uipath.platform.errors.EnrichedException`, which
already carries the status code and (truncated) response body as structured
fields.

Note: IXP is org/tenant-scoped only — it has no Orchestrator folder concept —
so this base deliberately does **not** inherit ``FolderContext``.
"""

from typing import Any, Optional, Union
from urllib.parse import quote

from httpx import HTTPStatusError, Response
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
)

from uipath.platform.constants import HEADER_USER_AGENT

from ..common._base_service import BaseService, _inject_trace_context
from ..common._models import Endpoint
from ..common._user_agent import user_agent_value
from ..common.retry import (
    MAX_RETRY_ATTEMPTS,
    is_retryable_platform_exception,
    platform_wait_strategy,
)
from ..errors import EnrichedException

#: API segment every design-time request is prefixed with.
DESIGNTIME_API_BASE = "du_/api/designtimeapi"

#: The only api-version the gateway currently accepts; sent on every call.
DESIGNTIME_API_VERSION = "1.0"


class IxpDesigntimeService(BaseService):
    """Base class for IXP design-time services (``du_/api/designtimeapi``).

    Subclasses build endpoints with :meth:`_endpoint` and issue requests with
    the ``_get`` / ``_post`` / ``_put`` / ``_patch`` / ``_delete`` / ``_upload``
    / ``_download`` helpers (each has an ``_async`` twin). Every helper appends
    the mandatory ``api-version`` query parameter; GETs are retried per the
    platform policy while writes and deletes are not (see module docstring).
    """

    def _endpoint(self, template: str, **segments: Any) -> Endpoint:
        """Build a design-time endpoint, percent-encoding dynamic segments.

        Args:
            template: Path template rooted at the API (e.g.
                ``"/api/projects/{name}/models/{version}/metrics"``). Fixed
                segments are kept verbatim; ``{placeholder}`` values are filled
                from ``segments``.
            **segments: Values substituted into the template, each encoded with
                ``quote(safe="")`` so reserved characters (``/``, spaces, ...)
                survive as ``%2F`` / ``%20``.

        Returns:
            The normalized ``Endpoint`` under ``du_/api/designtimeapi``.
        """
        encoded = {key: quote(str(value), safe="") for key, value in segments.items()}
        return Endpoint(f"/{DESIGNTIME_API_BASE}{template.format(**encoded)}")

    @staticmethod
    def _params(params: Optional[dict[str, Any]]) -> dict[str, Any]:
        """Merge the mandatory ``api-version`` into a request's query params."""
        return {"api-version": DESIGNTIME_API_VERSION, **(params or {})}

    @staticmethod
    def _raise_for_status(response: Response) -> Response:
        """Raise :class:`EnrichedException` on a non-2xx response."""
        try:
            response.raise_for_status()
        except HTTPStatusError as error:
            raise EnrichedException(error) from error
        return response

    def _headers(self) -> dict[str, str]:
        """Per-request headers: user-agent + trace context (auth is on the client)."""
        headers: dict[str, str] = {
            HEADER_USER_AGENT: user_agent_value(self._specific_component)
        }
        _inject_trace_context(headers)
        return headers

    # ── low-level send (no retry) ────────────────────────────────────────────

    def _send(
        self,
        method: str,
        endpoint: Union[Endpoint, str],
        *,
        params: Optional[dict[str, Any]] = None,
        json: Optional[Any] = None,
        files: Optional[dict[str, Any]] = None,
    ) -> Response:
        scoped_url = self._url.scope_url(str(endpoint), "tenant")
        response = self._client.request(
            method,
            scoped_url,
            params=self._params(params),
            json=json,
            files=files,
            headers=self._headers(),
        )
        return self._raise_for_status(response)

    async def _send_async(
        self,
        method: str,
        endpoint: Union[Endpoint, str],
        *,
        params: Optional[dict[str, Any]] = None,
        json: Optional[Any] = None,
        files: Optional[dict[str, Any]] = None,
    ) -> Response:
        scoped_url = self._url.scope_url(str(endpoint), "tenant")
        response = await self._client_async.request(
            method,
            scoped_url,
            params=self._params(params),
            json=json,
            files=files,
            headers=self._headers(),
        )
        return self._raise_for_status(response)

    # ── retrying send (idempotent GET only) ──────────────────────────────────

    @retry(
        retry=retry_if_exception(is_retryable_platform_exception),
        wait=platform_wait_strategy,
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        reraise=True,
    )
    def _send_retrying(
        self,
        method: str,
        endpoint: Union[Endpoint, str],
        *,
        params: Optional[dict[str, Any]] = None,
    ) -> Response:
        return self._send(method, endpoint, params=params)

    @retry(
        retry=retry_if_exception(is_retryable_platform_exception),
        wait=platform_wait_strategy,
        stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
        reraise=True,
    )
    async def _send_retrying_async(
        self,
        method: str,
        endpoint: Union[Endpoint, str],
        *,
        params: Optional[dict[str, Any]] = None,
    ) -> Response:
        return await self._send_async(method, endpoint, params=params)

    # ── verb helpers ─────────────────────────────────────────────────────────

    def _get(
        self, endpoint: Union[Endpoint, str], *, params: Optional[dict[str, Any]] = None
    ) -> Response:
        """GET (idempotent — retried per the platform policy)."""
        return self._send_retrying("GET", endpoint, params=params)

    async def _get_async(
        self, endpoint: Union[Endpoint, str], *, params: Optional[dict[str, Any]] = None
    ) -> Response:
        """Async GET (idempotent — retried per the platform policy)."""
        return await self._send_retrying_async("GET", endpoint, params=params)

    def _post(
        self,
        endpoint: Union[Endpoint, str],
        *,
        body: Optional[Any] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> Response:
        """POST (not retried). A ``None`` body is sent as ``{}`` (matching the CLI SDK)."""
        return self._send(
            "POST", endpoint, params=params, json=body if body is not None else {}
        )

    async def _post_async(
        self,
        endpoint: Union[Endpoint, str],
        *,
        body: Optional[Any] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> Response:
        """Async POST (not retried). A ``None`` body is sent as ``{}``."""
        return await self._send_async(
            "POST", endpoint, params=params, json=body if body is not None else {}
        )

    def _put(
        self,
        endpoint: Union[Endpoint, str],
        *,
        body: Optional[Any] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> Response:
        """PUT (not retried). A ``None`` body is sent as ``{}``."""
        return self._send(
            "PUT", endpoint, params=params, json=body if body is not None else {}
        )

    async def _put_async(
        self,
        endpoint: Union[Endpoint, str],
        *,
        body: Optional[Any] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> Response:
        """Async PUT (not retried). A ``None`` body is sent as ``{}``."""
        return await self._send_async(
            "PUT", endpoint, params=params, json=body if body is not None else {}
        )

    def _patch(
        self,
        endpoint: Union[Endpoint, str],
        *,
        body: Optional[Any] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> Response:
        """PATCH (not retried). A ``None`` body is sent as ``{}``."""
        return self._send(
            "PATCH", endpoint, params=params, json=body if body is not None else {}
        )

    async def _patch_async(
        self,
        endpoint: Union[Endpoint, str],
        *,
        body: Optional[Any] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> Response:
        """Async PATCH (not retried). A ``None`` body is sent as ``{}``."""
        return await self._send_async(
            "PATCH", endpoint, params=params, json=body if body is not None else {}
        )

    def _delete(
        self, endpoint: Union[Endpoint, str], *, params: Optional[dict[str, Any]] = None
    ) -> Response:
        """DELETE (not retried — avoids a spurious 404 from a retried delete)."""
        return self._send("DELETE", endpoint, params=params)

    async def _delete_async(
        self, endpoint: Union[Endpoint, str], *, params: Optional[dict[str, Any]] = None
    ) -> Response:
        """Async DELETE (not retried)."""
        return await self._send_async("DELETE", endpoint, params=params)

    def _upload(
        self,
        endpoint: Union[Endpoint, str],
        *,
        filename: str,
        content: Any,
        content_type: str = "application/octet-stream",
        params: Optional[dict[str, Any]] = None,
    ) -> Response:
        """Multipart upload of a single file under the ``file`` field (not retried)."""
        return self._send(
            "POST",
            endpoint,
            params=params,
            files={"file": (filename, content, content_type)},
        )

    async def _upload_async(
        self,
        endpoint: Union[Endpoint, str],
        *,
        filename: str,
        content: Any,
        content_type: str = "application/octet-stream",
        params: Optional[dict[str, Any]] = None,
    ) -> Response:
        """Async multipart upload under the ``file`` field (not retried)."""
        return await self._send_async(
            "POST",
            endpoint,
            params=params,
            files={"file": (filename, content, content_type)},
        )

    def _download(
        self, endpoint: Union[Endpoint, str], *, params: Optional[dict[str, Any]] = None
    ) -> tuple[bytes, str]:
        """GET raw bytes, returning ``(content, content_type)``."""
        response = self._send_retrying("GET", endpoint, params=params)
        content_type = (
            response.headers.get("content-type") or "application/octet-stream"
        )
        return response.content, content_type

    async def _download_async(
        self, endpoint: Union[Endpoint, str], *, params: Optional[dict[str, Any]] = None
    ) -> tuple[bytes, str]:
        """Async GET raw bytes, returning ``(content, content_type)``."""
        response = await self._send_retrying_async("GET", endpoint, params=params)
        content_type = (
            response.headers.get("content-type") or "application/octet-stream"
        )
        return response.content, content_type
