"""Integration Service: connector activity execution and vendor HTTP requests."""

import asyncio
import time
from typing import Any, Dict, Optional, Sequence
from urllib.parse import urlsplit

from httpx import Response, TransportError
from uipath.core.tracing import traced

from ..common._base_service import BaseService, _inject_trace_context
from ..common._bindings import resource_override
from ..common._config import UiPathApiConfig, UiPathConfig
from ..common._execution_context import UiPathExecutionContext
from ..common._folder_context import header_folder
from ..common._service_url_overrides import (
    inject_routing_headers,
    resolve_service_url,
)
from ..common._user_agent import user_agent_value
from ..common.retry import (
    RETRYABLE_STATUS_CODES,
    exponential_backoff_with_jitter,
    parse_retry_after,
)
from ..constants import HEADER_USER_AGENT
from . import execution as _exec
from .execution_types import (
    ExecuteActivityResult,
    ExecuteFile,
    ExecuteHttpResult,
    ExecuteResult,
)

HEADER_ORIGINATOR = "x-uipath-originator"
HEADER_SOURCE = "x-uipath-source"
# Lets GenAI activities be stitched back to the parent job for licensing attribution.
HEADER_ACTIVITY_JOB_ID = "x-uipath-job-id"
_ORIGINATOR_VALUE = "uipath-python"

# Statuses of the Integration Service call that an opted-in retry sends again.
_EXECUTE_RETRYABLE_STATUS_CODES = RETRYABLE_STATUS_CODES | {500}
_EXECUTE_INITIAL_BACKOFF = 0.5
_EXECUTE_MAX_BACKOFF = 10.0


# The arguments of an execute call that are safe to record in a trace. The body,
# headers, query parameters and files can carry secrets or personal data.
_TRACED_INPUTS = frozenset(
    {
        "connection_id",
        "object_name",
        "method",
        "connector_version",
        "connector_key",
        "script_ref",
        "folder_key",
        "folder_path",
        "file_response",
        "max_records",
        "max_retries",
        "retry_methods",
        "timeout",
    }
)


def _traced_inputs(inputs: Any) -> Dict[str, Any]:
    """Keep only the non-sensitive arguments of an execute call in the trace."""
    if not isinstance(inputs, dict):
        return {}
    traced_inputs = {
        key: value for key, value in inputs.items() if key in _TRACED_INPUTS
    }
    url = inputs.get("url")
    if isinstance(url, str):
        # Scheme, host and path only: a query string or userinfo can hold a secret
        try:
            parts = urlsplit(url)
            host = parts.hostname or ""
            origin = f"{parts.scheme}://{host}" if parts.scheme and host else ""
            traced_inputs["url"] = f"{origin}{parts.path}"
        except ValueError:
            traced_inputs["url"] = "<unreadable url>"
    return traced_inputs


class IntegrationService(BaseService):
    """Service for running Integration Service connector operations.

    Runs a connector activity (`execute_activity`) or sends a raw HTTP request
    to the vendor behind a connection (`execute_http`). Neither raises on a
    non-2xx response: the result carries the status and the vendor's body.

    For looking connections up and fetching their tokens, see
    `ConnectionsService` (`sdk.connections`).
    """

    def __init__(
        self,
        config: UiPathApiConfig,
        execution_context: UiPathExecutionContext,
    ) -> None:
        super().__init__(config=config, execution_context=execution_context)

    @resource_override(
        "connection",
        resource_identifier="connection_id",
        folder_identifier="folder_key",
    )
    @traced(
        name="integration_service_execute_activity",
        run_type="uipath",
        input_processor=_traced_inputs,
        hide_output=True,
    )
    def execute_activity(
        self,
        connection_id: str,
        object_name: str,
        method: str = "GET",
        *,
        body: Any = None,
        query_params: Optional[Dict[str, str]] = None,
        files: Optional[Sequence[ExecuteFile]] = None,
        body_part_name: Optional[str] = None,
        url_input_fields: Optional[Sequence[str]] = None,
        file_response: bool = False,
        max_records: Optional[int] = None,
        connector_version: Optional[str] = None,
        connector_key: Optional[str] = None,
        script_ref: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
        max_retries: int = 0,
        retry_methods: Optional[Sequence[str]] = None,
        timeout: Optional[float] = None,
    ) -> ExecuteActivityResult:
        """Run a connector activity: one operation on a connector object.

        Calls `elements_/v3/element/instances/{connection_id}/{object_name}`, or
        the version 4 engine when `connector_version` is 4 or later, and adds what a connector activity needs: body keys given as paths, file
        upload and download, paging, and query parameters that take a URL.

        Unlike most SDK methods, **this does not raise on a non-2xx response**.
        The full HTTP envelope is returned so the caller can read the
        connector's error body. Check `ok` and `status`.

        Preview: this method is experimental and may change.

        Args:
            connection_id: The connection's id.
            object_name: Connector object name, e.g. `tickets`. May be a
                multi-segment path such as `curated_get_issue/ABC-1`.
            method: HTTP method: `GET`, `POST`, `PUT`, `PATCH` or `DELETE`.
            body: Body for `POST`, `PUT` or `PATCH`, sent as JSON. A top-level
                key of a dict can be a path: `{"fields.summary": "x"}` is sent
                as `{"fields": {"summary": "x"}}`. A path can address an array
                item (`items[0].name`) or every item (`items[*].name`). A
                write sent without a body carries `{}`.
            query_params: Query string parameters.
            files: Files to upload. The call is sent as a multipart form with
                one part per file, and a non-empty `body` travels as a JSON
                part named by `body_part_name`.
            body_part_name: Name of the form part that carries `body` when
                `files` is set. Defaults to `body`.
            url_input_fields: Names of the query parameters the connector
                marks as accepting a URL. A listed parameter whose value is an
                http or https URL is sent Base64-encoded.
            file_response: Read a successful response as a file: `body` is
                `bytes` whatever content type the connector reports. Without
                it a file is still detected from the response headers.
            max_records: How many records a `GET` list call should return in
                total. The call follows the connector's pages until it has
                this many records or the list ends. Pass `-1` for every
                record. Without it a single page is returned, with `page` set
                on the result when more records exist.
            connector_version: Version of the connector behind the connection,
                e.g. `4.0.0`. A connector of version 4 or later runs its
                activities on the version 4 engine (`elements_/v4/execute`),
                and the call is sent there; without a version, or with an
                earlier one, the call uses the version 3 engine. The SDK does
                not look the version up. On the version 4 engine `object_name`
                names the activity's script, `files` is refused, and
                `file_response`, `url_input_fields` and `max_records` do not
                apply.
            connector_key: Key of the connector behind the connection, e.g.
                `uipath-salesforce-slack`. Required on the version 4 engine.
            script_ref: Reference of the script the version 4 engine runs for
                this activity, as the activity's metadata names it. Defaults
                to `object_name`.
            headers: Headers the activity's script reads from the call.
                Version 4 engine only.
            folder_key: Key of the folder the connection is in.
            folder_path: Path of the folder the connection is in. Mutually
                exclusive with `folder_key`.
            max_retries: How many times to send a failed call again. Off by
                default.
            retry_methods: Methods that may be retried. Defaults to the
                idempotent ones (`GET`, `PUT`, `DELETE`): a replayed `POST`
                can create the same record twice.
            timeout: Timeout of a single attempt, in seconds.

        Returns:
            ExecuteActivityResult: The response envelope, whatever its status.

        Raises:
            ValueError: If an argument is missing or invalid.

        Examples:
            >>> result = sdk.integration_service.execute_activity("<connection-id>", "tickets")
            >>> if result.ok:
            ...     print(result.body)

            >>> sdk.integration_service.execute_activity(
            ...     "<connection-id>", "tickets", "POST",
            ...     body={"subject": "New ticket", "fields.priority": "high"},
            ... )

            >>> everything = sdk.integration_service.execute_activity(
            ...     "<connection-id>", "tickets", max_records=-1
            ... )

            >>> # A connector of version 4 or later: pass its version and key
            >>> sdk.integration_service.execute_activity(
            ...     "<connection-id>", "SendMessageToChannel", "POST",
            ...     connector_version="4.0.0",
            ...     connector_key="uipath-salesforce-slack",
            ...     query_params={"send_as": "bot"},
            ...     body={"channel": "<channel-id>", "messageToSend": "Hello"},
            ... )
        """
        request, limit, on_v4 = self._activity_request(
            connection_id,
            object_name,
            method,
            body=body,
            query_params=query_params,
            files=files,
            body_part_name=body_part_name,
            url_input_fields=url_input_fields,
            file_response=file_response,
            max_records=max_records,
            connector_version=connector_version,
            connector_key=connector_key,
            script_ref=script_ref,
            headers=headers,
            folder_key=folder_key,
            folder_path=folder_path,
            max_retries=max_retries,
            retry_methods=retry_methods,
            timeout=timeout,
        )

        first = self._send_execute(request)
        if on_v4:
            return _exec.to_v4_activity_result(first)
        if limit is None or not _exec.needs_paging(request.method, limit, first):
            return _exec.to_activity_result(first)

        records = list(first.body)
        last = first
        followed = False
        page = _exec.extract_page(first.headers, first.body)
        while page and page.has_more and len(records) < limit:
            following = self._send_execute(_exec.next_page_request(request, page))
            if not following.ok:
                # A page that fails is the result, so the caller sees the failure
                return _exec.to_activity_result(following)
            followed = True
            last = following
            if isinstance(following.body, list):
                records.extend(following.body)
            page = _exec.extract_page(following.headers, following.body)
        return _exec.gathered_result(first, last, records, limit, followed)

    @resource_override(
        "connection",
        resource_identifier="connection_id",
        folder_identifier="folder_key",
    )
    @traced(
        name="integration_service_execute_activity",
        run_type="uipath",
        input_processor=_traced_inputs,
        hide_output=True,
    )
    async def execute_activity_async(
        self,
        connection_id: str,
        object_name: str,
        method: str = "GET",
        *,
        body: Any = None,
        query_params: Optional[Dict[str, str]] = None,
        files: Optional[Sequence[ExecuteFile]] = None,
        body_part_name: Optional[str] = None,
        url_input_fields: Optional[Sequence[str]] = None,
        file_response: bool = False,
        max_records: Optional[int] = None,
        connector_version: Optional[str] = None,
        connector_key: Optional[str] = None,
        script_ref: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
        max_retries: int = 0,
        retry_methods: Optional[Sequence[str]] = None,
        timeout: Optional[float] = None,
    ) -> ExecuteActivityResult:
        """Asynchronously run a connector activity.

        The asynchronous form of `execute_activity`: same arguments, same
        result, and it does not raise on a non-2xx response either.

        Preview: this method is experimental and may change.

        Args:
            connection_id: The connection's id.
            object_name: Connector object name, e.g. `tickets`.
            method: HTTP method: `GET`, `POST`, `PUT`, `PATCH` or `DELETE`.
            body: Body for `POST`, `PUT` or `PATCH`. Top-level keys of a dict
                can be paths, e.g. `fields.summary`.
            query_params: Query string parameters.
            files: Files to upload as a multipart form.
            body_part_name: Name of the form part that carries `body` when
                `files` is set. Defaults to `body`.
            url_input_fields: Names of the query parameters that take a URL.
            file_response: Read a successful response as `bytes`.
            max_records: Total records a `GET` list call should gather across
                pages; `-1` for every record.
            connector_version: Version of the connector behind the connection;
                4 or later selects the version 4 engine.
            connector_key: Key of the connector behind the connection.
                Required on the version 4 engine.
            script_ref: Reference of the script the version 4 engine runs.
                Defaults to `object_name`.
            headers: Headers the activity's script reads (version 4 only).
            folder_key: Key of the folder the connection is in.
            folder_path: Path of the folder the connection is in.
            max_retries: How many times to send a failed call again.
            retry_methods: Methods that may be retried.
            timeout: Timeout of a single attempt, in seconds.

        Returns:
            ExecuteActivityResult: The response envelope, whatever its status.

        Raises:
            ValueError: If an argument is missing or invalid.

        Examples:
            >>> result = await sdk.integration_service.execute_activity_async(
            ...     "<connection-id>", "tickets"
            ... )
        """
        request, limit, on_v4 = self._activity_request(
            connection_id,
            object_name,
            method,
            body=body,
            query_params=query_params,
            files=files,
            body_part_name=body_part_name,
            url_input_fields=url_input_fields,
            file_response=file_response,
            max_records=max_records,
            connector_version=connector_version,
            connector_key=connector_key,
            script_ref=script_ref,
            headers=headers,
            folder_key=folder_key,
            folder_path=folder_path,
            max_retries=max_retries,
            retry_methods=retry_methods,
            timeout=timeout,
        )

        first = await self._send_execute_async(request)
        if on_v4:
            return _exec.to_v4_activity_result(first)
        if limit is None or not _exec.needs_paging(request.method, limit, first):
            return _exec.to_activity_result(first)

        records = list(first.body)
        last = first
        followed = False
        page = _exec.extract_page(first.headers, first.body)
        while page and page.has_more and len(records) < limit:
            following = await self._send_execute_async(
                _exec.next_page_request(request, page)
            )
            if not following.ok:
                # A page that fails is the result, so the caller sees the failure
                return _exec.to_activity_result(following)
            followed = True
            last = following
            if isinstance(following.body, list):
                records.extend(following.body)
            page = _exec.extract_page(following.headers, following.body)
        return _exec.gathered_result(first, last, records, limit, followed)

    @resource_override(
        "connection",
        resource_identifier="connection_id",
        folder_identifier="folder_key",
    )
    @traced(
        name="integration_service_execute_http",
        run_type="uipath",
        input_processor=_traced_inputs,
        hide_output=True,
    )
    def execute_http(
        self,
        connection_id: str,
        url: str,
        method: str = "GET",
        *,
        headers: Optional[Dict[str, str]] = None,
        query_params: Optional[Dict[str, str]] = None,
        body: Any = None,
        connector_version: Optional[str] = None,
        connector_key: Optional[str] = None,
        file: Optional[ExecuteFile] = None,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
        max_retries: int = 0,
        retry_methods: Optional[Sequence[str]] = None,
        timeout: Optional[float] = None,
    ) -> ExecuteHttpResult:
        """Send an HTTP request to a vendor API through a connection.

        Integration Service adds the connection's authentication, so the
        vendor's key or token never reaches your code. Use this for a vendor
        endpoint the connector has no object for; for a connector object use
        `execute_activity`.

        The result describes the vendor's response. **This does not raise on a
        non-2xx response**: check `ok`, and `is_vendor_error` to tell a vendor
        error from a call that never reached the vendor.

        Preview: this method is experimental and may change.

        Args:
            connection_id: The connection's id.
            url: Vendor URL. A path such as `/v2/tickets` is resolved against
                the connection's base URL. On the version 4 engine it must be
                a full URL.
            method: HTTP method to send to the vendor.
            headers: Headers to send to the vendor.
            query_params: Query string parameters to send to the vendor.
            body: Body to send to the vendor. A string is sent as is; anything
                else is serialized as JSON.
            connector_version: Version of the connector behind the connection,
                e.g. `4.0.0`. A connector of version 4 or later runs on the
                version 4 engine (`elements_/v4/execute`); without a version,
                or with an earlier one, the call uses the version 3
                passthrough. The SDK does not look the version up.
            connector_key: Key of the connector behind the connection, e.g.
                `uipath-zendesk`. Used on the version 4 engine.
            file: A file to send as the whole body of the vendor request.
                Needs a version 4 connector, and cannot be combined with
                `body`.
            folder_key: Key of the folder the connection is in.
            folder_path: Path of the folder the connection is in. Mutually
                exclusive with `folder_key`.
            max_retries: How many times to send a failed call again. Off by
                default. Only a failure of the Integration Service call itself
                is retried; a vendor error status is returned as the result.
            retry_methods: Vendor methods that may be retried. Defaults to the
                idempotent ones, so a `GET` is retried and a `POST` is not.
            timeout: Timeout of a single attempt, in seconds.

        Returns:
            ExecuteHttpResult: The vendor's response, or the Integration
                Service response when the call did not reach the vendor.

        Raises:
            ValueError: If an argument is missing or invalid, or a version 4
                file response arrives incomplete.

        Examples:
            >>> result = sdk.integration_service.execute_http("<connection-id>", "/v2/tickets")
            >>> if result.ok:
            ...     print(result.body)
            ... elif result.is_vendor_error:
            ...     print(f"Vendor returned {result.status}: {result.body}")

            >>> sdk.integration_service.execute_http(
            ...     "<connection-id>", "https://api.example.com/v2/tickets", "POST",
            ...     body={"subject": "New ticket"},
            ...     connector_version="4.0.0",
            ... )
        """
        request, on_v4 = self._http_request(
            connection_id,
            url,
            method,
            headers=headers,
            query_params=query_params,
            body=body,
            connector_version=connector_version,
            connector_key=connector_key,
            file=file,
            folder_key=folder_key,
            folder_path=folder_path,
            max_retries=max_retries,
            retry_methods=retry_methods,
            timeout=timeout,
        )
        result = self._send_execute(request)
        return (
            _exec.unwrap_v4_response(result)
            if on_v4
            else _exec.unwrap_proxy_response(result)
        )

    @resource_override(
        "connection",
        resource_identifier="connection_id",
        folder_identifier="folder_key",
    )
    @traced(
        name="integration_service_execute_http",
        run_type="uipath",
        input_processor=_traced_inputs,
        hide_output=True,
    )
    async def execute_http_async(
        self,
        connection_id: str,
        url: str,
        method: str = "GET",
        *,
        headers: Optional[Dict[str, str]] = None,
        query_params: Optional[Dict[str, str]] = None,
        body: Any = None,
        connector_version: Optional[str] = None,
        connector_key: Optional[str] = None,
        file: Optional[ExecuteFile] = None,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
        max_retries: int = 0,
        retry_methods: Optional[Sequence[str]] = None,
        timeout: Optional[float] = None,
    ) -> ExecuteHttpResult:
        """Asynchronously send an HTTP request to a vendor API through a connection.

        The asynchronous form of `execute_http`: same arguments, same result,
        and it does not raise on a non-2xx response either.

        Preview: this method is experimental and may change.

        Args:
            connection_id: The connection's id.
            url: Vendor URL, or a path resolved against the connection's base
                URL. A full URL on the version 4 engine.
            method: HTTP method to send to the vendor.
            headers: Headers to send to the vendor.
            query_params: Query string parameters to send to the vendor.
            body: Body to send to the vendor.
            connector_version: Version of the connector behind the connection;
                4 or later selects the version 4 engine.
            connector_key: Key of the connector behind the connection.
            file: A file to send as the whole body (version 4 only).
            folder_key: Key of the folder the connection is in.
            folder_path: Path of the folder the connection is in.
            max_retries: How many times to send a failed call again.
            retry_methods: Vendor methods that may be retried.
            timeout: Timeout of a single attempt, in seconds.

        Returns:
            ExecuteHttpResult: The vendor's response, or the Integration
                Service response when the call did not reach the vendor.

        Raises:
            ValueError: If an argument is missing or invalid, or a version 4
                file response arrives incomplete.

        Examples:
            >>> result = await sdk.integration_service.execute_http_async(
            ...     "<connection-id>", "/v2/tickets"
            ... )
        """
        request, on_v4 = self._http_request(
            connection_id,
            url,
            method,
            headers=headers,
            query_params=query_params,
            body=body,
            connector_version=connector_version,
            connector_key=connector_key,
            file=file,
            folder_key=folder_key,
            folder_path=folder_path,
            max_retries=max_retries,
            retry_methods=retry_methods,
            timeout=timeout,
        )
        result = await self._send_execute_async(request)
        return (
            _exec.unwrap_v4_response(result)
            if on_v4
            else _exec.unwrap_proxy_response(result)
        )

    def _activity_request(
        self,
        connection_id: str,
        object_name: str,
        method: str,
        *,
        body: Any,
        query_params: Optional[Dict[str, str]],
        files: Optional[Sequence[ExecuteFile]],
        body_part_name: Optional[str],
        url_input_fields: Optional[Sequence[str]],
        file_response: bool,
        max_records: Optional[int],
        connector_version: Optional[str],
        connector_key: Optional[str],
        script_ref: Optional[str],
        headers: Optional[Dict[str, str]],
        folder_key: Optional[str],
        folder_path: Optional[str],
        max_retries: int,
        retry_methods: Optional[Sequence[str]],
        timeout: Optional[float],
    ) -> tuple[_exec.ExecuteRequest, Optional[float], bool]:
        """Validate the arguments of `execute_activity` and build its request."""
        caller = "execute_activity"
        if not connection_id:
            raise ValueError(f"connection_id is required for {caller}")
        if not object_name:
            raise ValueError(f"object_name is required for {caller}")
        method = _exec.normalize_method(method, caller)
        limit = _exec.resolve_max_records(max_records, caller)
        if files:
            _exec.validate_files(files, caller)

        if isinstance(body, dict):
            body = _exec.expand_body_paths(body)

        if _exec.uses_v4_engine(connector_version):
            if files:
                raise ValueError(
                    f"files are not supported by {caller} on a version 4 connector"
                )
            if not connector_key:
                raise ValueError(
                    f"connector_key is required for {caller} on a version 4 connector"
                )
            v4_request = _exec.ExecuteRequest(
                # The activity always travels in a POST; `method` is the
                # activity's own operation, and the retry settings describe it.
                method="POST",
                endpoint=_exec.ELEMENT_V4_EXECUTE,
                body=_exec.build_v4_activity_manifest(
                    connection_id=connection_id,
                    connector_key=connector_key,
                    script_ref=script_ref or object_name,
                    body=body,
                    query_params=query_params,
                    headers=headers,
                ),
                has_body=True,
                folder_key=folder_key,
                folder_path=folder_path,
                max_retries=max_retries,
                retryable=_exec.is_retryable_method(method, retry_methods),
                timeout=timeout,
            )
            return v4_request, None, True

        writes = method in _exec.BODY_METHODS
        request = _exec.ExecuteRequest(
            method=method,
            endpoint=_exec.activity_endpoint(connection_id, object_name),
            params=_exec.encode_url_inputs(query_params, url_input_fields),
            # Integration Service rejects a write that arrives with no body at all
            body={} if body is None and writes else body,
            has_body=writes and not files,
            files=_exec.build_multipart(files, body, body_part_name) if files else None,
            file_response=file_response,
            folder_key=folder_key,
            folder_path=folder_path,
            max_retries=max_retries,
            retryable=_exec.is_retryable_method(method, retry_methods),
            timeout=timeout,
        )
        return request, limit, False

    def _http_request(
        self,
        connection_id: str,
        url: str,
        method: str,
        *,
        headers: Optional[Dict[str, str]],
        query_params: Optional[Dict[str, str]],
        body: Any,
        connector_version: Optional[str],
        connector_key: Optional[str],
        file: Optional[ExecuteFile],
        folder_key: Optional[str],
        folder_path: Optional[str],
        max_retries: int,
        retry_methods: Optional[Sequence[str]],
        timeout: Optional[float],
    ) -> tuple[_exec.ExecuteRequest, bool]:
        """Validate the arguments of `execute_http` and build its request."""
        caller = "execute_http"
        if not connection_id:
            raise ValueError(f"connection_id is required for {caller}")
        if not url:
            raise ValueError(f"url is required for {caller}")
        method = _exec.normalize_method(method, caller)

        on_v4 = _exec.uses_v4_engine(connector_version)
        if file is not None:
            if not on_v4:
                raise ValueError(
                    "file needs a version 4 connector: pass connector_version"
                )
            if body is not None:
                raise ValueError(f"file and body cannot both be passed to {caller}")
            _exec.validate_files([file], caller)

        # The vendor request always travels in a POST; the caller's retry
        # settings describe the vendor request.
        request = _exec.ExecuteRequest(
            method="POST",
            endpoint="",
            has_body=True,
            folder_key=folder_key,
            folder_path=folder_path,
            max_retries=max_retries,
            retryable=_exec.is_retryable_method(method, retry_methods),
            timeout=timeout,
        )

        if on_v4:
            manifest = _exec.build_v4_manifest(
                connection_id=connection_id,
                connector_key=connector_key,
                method=method,
                url=url,
                headers=headers,
                query_params=query_params,
                body=body,
                file=file,
            )
            request.endpoint = _exec.ELEMENT_V4_EXECUTE
            request.body = manifest
            if file is not None:
                request.has_body = False
                request.files = _exec.build_v4_upload(manifest, file)
        else:
            request.endpoint = _exec.http_request_endpoint(connection_id)
            request.body = _exec.build_proxy_body(
                method, url, headers, query_params, body
            )
        return request, on_v4

    def _execute_call(
        self, request: _exec.ExecuteRequest
    ) -> tuple[str, Dict[str, Any]]:
        """The URL and httpx arguments of one execute call."""
        headers: Dict[str, str] = {
            HEADER_ORIGINATOR: _ORIGINATOR_VALUE,
            HEADER_SOURCE: _ORIGINATOR_VALUE,
            **header_folder(request.folder_key, request.folder_path),
            HEADER_USER_AGENT: user_agent_value("IntegrationService.execute"),
        }
        if job_key := UiPathConfig.job_key:
            headers[HEADER_ACTIVITY_JOB_ID] = job_key
        _inject_trace_context(headers)

        override = resolve_service_url(request.endpoint)
        if override:
            url = override
            inject_routing_headers(headers)
        else:
            url = self._url.scope_url(request.endpoint, "tenant")

        kwargs: Dict[str, Any] = {"headers": headers}
        if request.params:
            kwargs["params"] = request.params
        if request.files:
            kwargs["files"] = request.files
        elif request.has_body:
            kwargs["json"] = request.body
        if request.timeout is not None:
            kwargs["timeout"] = request.timeout
        return url, kwargs

    @staticmethod
    def _execute_retry_delay(
        request: _exec.ExecuteRequest, attempt: int, response: Optional[Response]
    ) -> Optional[float]:
        """Seconds to wait before sending a failed call again, or None to stop."""
        if not request.retryable or attempt > request.max_retries:
            return None
        if response is not None:
            if response.status_code not in _EXECUTE_RETRYABLE_STATUS_CODES:
                return None
            retry_after = parse_retry_after(response.headers.get("retry-after", ""))
            if retry_after is not None:
                return min(retry_after, _EXECUTE_MAX_BACKOFF)
        return min(
            exponential_backoff_with_jitter(attempt, _EXECUTE_INITIAL_BACKOFF),
            _EXECUTE_MAX_BACKOFF,
        )

    def _send_execute(self, request: _exec.ExecuteRequest) -> ExecuteResult:
        """Send one execute call; a non-2xx response is returned, not raised."""
        url, kwargs = self._execute_call(request)
        attempt = 0
        while True:
            attempt += 1
            try:
                response = self._client.request(request.method, url, **kwargs)
            except TransportError:
                delay = self._execute_retry_delay(request, attempt, None)
                if delay is None:
                    raise
            else:
                delay = self._execute_retry_delay(request, attempt, response)
                if delay is None:
                    return _exec.to_result(response, request.file_response)
            time.sleep(delay)

    async def _send_execute_async(self, request: _exec.ExecuteRequest) -> ExecuteResult:
        """Asynchronously send one execute call; a non-2xx response is returned."""
        url, kwargs = self._execute_call(request)
        attempt = 0
        while True:
            attempt += 1
            try:
                response = await self._client_async.request(
                    request.method, url, **kwargs
                )
            except TransportError:
                delay = self._execute_retry_delay(request, attempt, None)
                if delay is None:
                    raise
            else:
                delay = self._execute_retry_delay(request, attempt, response)
                if delay is None:
                    return _exec.to_result(response, request.file_response)
            await asyncio.sleep(delay)
