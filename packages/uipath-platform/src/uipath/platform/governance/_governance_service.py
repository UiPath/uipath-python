"""Service for the ``agenticgovernance_`` ingress.

Wraps the governance backend endpoints UiPath exposes:

- ``GET  /{org}/agenticgovernance_/api/v1/runtime/policy``  — fetch the
  tenant-managed policy pack (see :meth:`GovernanceService.retrieve_policy`).
- ``POST /{org}/agenticgovernance_/api/v1/runtime/govern``  — compensating
  governance call fired when a ``guardrail_fallback`` rule matches
  (see :meth:`GovernanceService.compensate`).

A third backend endpoint —
``POST /{org}/agenticgovernance_/api/v1/runtime/log`` — emits custom
telemetry events to App Insights. It's reached only through the
internal ``_track_event`` helper, which the runtime adapter
(:class:`UiPathPlatformGovernanceProvider`) calls; not part of the
client-facing service surface.

Org/tenant scoping is read from :class:`UiPathConfig`; auth, retries,
trace context, and error enrichment come from :class:`BaseService`.
"""

from typing import Any, Optional

from uipath.core import traced
from uipath.core.governance import (
    FiredRule,
    GovernRequest,
    PolicyContext,
    PolicyResponse,
)

from uipath.platform.constants import HEADER_INTERNAL_TENANT_ID

from ..common._base_service import BaseService, resolve_trace_id
from ..common._config import UiPathConfig
from ..common._service_url_overrides import (
    inject_routing_headers,
    resolve_service_url,
)

# The agenticgovernance_ ingress lives at a separate org-scoped path that
# uses the organization UUID (not the slug exposed by ``UIPATH_URL``).
GOVERNANCE_SERVICE_PREFIX = "agenticgovernance_"
POLICY_API_PATH = "api/v1/runtime/policy"
GOVERN_API_PATH = "api/v1/runtime/govern"
LOG_API_PATH = "api/v1/runtime/log"
AGENT_TYPE_PARAM = "agentType"

# Caller-set correlation id that becomes the App Insights ``operation_Id``
# stamped on every customEvent produced by the matching ``/runtime/log``
# request — see the spec on the platform-side ``postLogHandler``.
HEADER_OPERATION_ID = "x-uipath-operation-id"


class GovernanceService(BaseService):
    """Service for the agenticgovernance_ ingress.

    Exposes two endpoints:

    - :meth:`retrieve_policy` — GET the tenant-managed policy pack.
    - :meth:`compensate` — POST a compensating ``/runtime/govern`` call
      so the server can run a disabled centralized guardrail and write
      the per-rule LLMOps audit records itself.

    Org and tenant scoping come from :attr:`UiPathConfig.organization_id`
    and :attr:`UiPathConfig.tenant_id`; the tenant travels in the
    ``x-uipath-internal-tenantid`` header (the URL is org-scoped only).

    !!! info "Version Availability"
        This service is available starting from **uipath** version **2.2.13**.
    """

    # ── Policy fetch ─────────────────────────────────────────────────

    @traced(name="governance_retrieve_policy", run_type="uipath")
    def retrieve_policy(
        self,
        *,
        is_conversational: Optional[bool] = None,
    ) -> PolicyResponse:
        """Fetch the governance policy pack for the active org/tenant.

        Args:
            is_conversational: When the hosted agent's type is known,
                selects the conversational (``True``) or autonomous
                (``False``) policy view. ``None`` (default) omits the
                ``agentType`` query param so the server applies its
                default.

        Returns:
            PolicyResponse: ``mode`` and the YAML ``policies`` string.

        Raises:
            ValueError: If ``UiPathConfig.organization_id`` or
                ``UiPathConfig.tenant_id`` is not set.
            EnrichedException: If the backend returns a non-2xx response.

        Examples:
            ```python
            from uipath.platform import UiPath

            client = UiPath()
            response = client.governance.retrieve_policy()
            print(response.mode, len(response.policies))
            ```
        """
        url, headers = self._build_org_scoped_request(POLICY_API_PATH)
        params = self._policy_params(is_conversational)
        response = self.request("GET", url=url, params=params, headers=headers)
        return PolicyResponse.model_validate(response.json())

    @traced(name="governance_retrieve_policy", run_type="uipath")
    async def retrieve_policy_async(
        self,
        *,
        is_conversational: Optional[bool] = None,
    ) -> PolicyResponse:
        """Asynchronously fetch the governance policy pack.

        See :meth:`retrieve_policy` for parameter and return semantics.
        """
        url, headers = self._build_org_scoped_request(POLICY_API_PATH)
        params = self._policy_params(is_conversational)
        response = await self.request_async(
            "GET", url=url, params=params, headers=headers
        )
        return PolicyResponse.model_validate(response.json())

    # ── Policy provider adapter (GovernancePolicyProvider protocol) ─

    def get_policy(self, context: PolicyContext) -> PolicyResponse:
        """Fetch the policy pack — :class:`GovernancePolicyProvider` adapter.

        Thin wrapper over :meth:`retrieve_policy` that accepts the
        context model the core protocol uses. Lets the runtime consume
        governance through :class:`uipath.core.governance.GovernancePolicyProvider`
        without importing this module.
        """
        return self.retrieve_policy(is_conversational=context.is_conversational)

    async def get_policy_async(self, context: PolicyContext) -> PolicyResponse:
        """Async variant of :meth:`get_policy`."""
        return await self.retrieve_policy_async(
            is_conversational=context.is_conversational
        )

    # ── Compensating governance call ─────────────────────────────────

    def compensate(
        self,
        *,
        hook: str,
        validators: list[str],
        rules: list[FiredRule],
        data: dict[str, Any],
        src_timestamp: str,
        agent_name: str,
        runtime_id: str,
        trace_id: str | None = None,
        folder_key: str | None = None,
        job_key: str | None = None,
        process_key: str | None = None,
        reference_id: str | None = None,
        agent_version: str | None = None,
    ) -> None:
        """POST a compensating ``/runtime/govern`` call.

        Fired when a ``guardrail_fallback`` rule matches: the centralized
        guardrail is disabled, so the server is asked to run the
        guardrail check server-side and write the per-rule LLMOps audit
        records bound to the agent's trace. The agent does not inspect
        the response body.

        Job-context fields (``folder_key`` / ``job_key`` /
        ``process_key`` / ``reference_id`` / ``agent_version``) are
        auto-populated from :class:`UiPathConfig` when omitted.
        Caller-supplied values — including the empty string — take
        precedence.

        Args:
            hook: Identifier of the agent hook that fired the rule
                (e.g. ``"before_model"``).
            validators: Validator names attached to the fired rules.
            rules: Each rule that fired — one LLMOps audit record is
                written per entry.
            data: Hook payload the server replays through the
                centralized guardrail.
            trace_id: Canonical 32-char hex trace id. Optional — when
                ``None`` (default) the service resolves the value
                itself at call time via :func:`resolve_trace_id`.
                Callers that already hold a resolved id (typically
                captured on the hook thread before a background-pool
                hop) pass it in to win over the auto-resolve.
            src_timestamp: ISO-8601 timestamp on the source side.
            agent_name: Agent identifier as known to the platform.
            runtime_id: Runtime instance identifier.
            folder_key: Override the env-backed folder key.
            job_key: Override the env-backed job key.
            process_key: Override the env-backed process key.
            reference_id: Override the env-backed agent id.
            agent_version: Override the env-backed agent version.

        Raises:
            ValueError: If ``UiPathConfig.organization_id`` or
                ``UiPathConfig.tenant_id`` is not set.
            EnrichedException: If the backend returns a non-2xx response.

        Threading:
            OpenTelemetry context is thread-local; callers that
            background-pool the compensation call must capture the
            canonical trace id (via :func:`resolve_trace_id`) on the
            hook thread and pass it in explicitly — the auto-resolve
            on the worker thread will see a detached context.
        """
        self._compensate(
            GovernRequest(
                hook=hook,
                validators=validators,
                rules=rules,
                data=data,
                trace_id=trace_id,
                src_timestamp=src_timestamp,
                agent_name=agent_name,
                runtime_id=runtime_id,
                folder_key=folder_key,
                job_key=job_key,
                process_key=process_key,
                reference_id=reference_id,
                agent_version=agent_version,
            )
        )

    async def compensate_async(
        self,
        *,
        hook: str,
        validators: list[str],
        rules: list[FiredRule],
        data: dict[str, Any],
        src_timestamp: str,
        agent_name: str,
        runtime_id: str,
        trace_id: str | None = None,
        folder_key: str | None = None,
        job_key: str | None = None,
        process_key: str | None = None,
        reference_id: str | None = None,
        agent_version: str | None = None,
    ) -> None:
        """Asynchronously POST a compensating ``/runtime/govern`` call.

        See :meth:`compensate` for parameter semantics.
        """
        await self._compensate_async(
            GovernRequest(
                hook=hook,
                validators=validators,
                rules=rules,
                data=data,
                trace_id=trace_id,
                src_timestamp=src_timestamp,
                agent_name=agent_name,
                runtime_id=runtime_id,
                folder_key=folder_key,
                job_key=job_key,
                process_key=process_key,
                reference_id=reference_id,
                agent_version=agent_version,
            )
        )

    # ── Internal worker for GovernRequest-shaped callers ─────────────

    @traced(name="governance_compensate", run_type="uipath")
    def _compensate(self, request: GovernRequest) -> None:
        """Fire a compensation call from a pre-built :class:`GovernRequest`.

        Internal helper used by the provider adapter
        (:class:`uipath.platform.governance.UiPathPlatformGovernanceProvider`)
        to satisfy :class:`uipath.core.governance.GovernanceCompensationProvider`
        without unpacking the request. The public ergonomic counterpart
        is :meth:`compensate`.

        When ``request.trace_id`` is ``None`` the service resolves the
        canonical trace id itself via :func:`resolve_trace_id` — same
        fallback ``track_event`` uses. Callers that have a resolved
        value still pass it in; callers that don't (e.g. the runtime
        layer, which intentionally stays env-free) leave it ``None``
        and let the service do the work.
        """
        request = self._resolve_request_trace_id(request)
        url, headers = self._build_org_scoped_request(GOVERN_API_PATH)
        payload = self._build_govern_payload(request)
        self.request("POST", url=url, headers=headers, json=payload)

    @traced(name="governance_compensate", run_type="uipath")
    async def _compensate_async(self, request: GovernRequest) -> None:
        """Async variant of :meth:`_compensate`.

        Same ``trace_id`` self-resolution behavior as the sync variant.
        """
        request = self._resolve_request_trace_id(request)
        url, headers = self._build_org_scoped_request(GOVERN_API_PATH)
        payload = self._build_govern_payload(request)
        await self.request_async("POST", url=url, headers=headers, json=payload)

    @staticmethod
    def _resolve_request_trace_id(request: GovernRequest) -> GovernRequest:
        """Fill ``request.trace_id`` from :func:`resolve_trace_id` when absent.

        Caller-supplied values (including ``""``) win — the runtime
        captures on the hook thread (via ``contextvars.copy_context``
        for the background pool) and the resolver here only fires when
        the field was left ``None``.
        """
        if request.trace_id is not None:
            return request
        resolved = resolve_trace_id()
        if not resolved:
            return request
        return request.model_copy(update={"trace_id": resolved})

    # ── Custom telemetry events (internal runtime seam) ──────────────
    #
    # ``_track_event`` / ``_track_event_async`` are intentionally
    # underscore-prefixed: they exist for the runtime adapter
    # (:class:`UiPathPlatformGovernanceProvider`) to fire telemetry
    # events through the platform's HTTP stack, not as a client-facing
    # SDK call. Keeping them off the public surface keeps the auto-
    # generated docs (``mkdocs`` + ``mkdocstrings``) focused on the
    # endpoints customers consume directly (``retrieve_policy`` /
    # ``compensate``).

    def _track_event(
        self,
        *,
        event_name: str,
        data: dict[str, Any] | None = None,
        operation_id: str | None = None,
    ) -> None:
        """POST a custom telemetry event to ``/runtime/log``.

        Internal seam — the runtime adapter
        (:class:`UiPathPlatformGovernanceProvider`) calls this to emit
        governance audit events through the platform's HTTP stack.
        The server forwards the event to App Insights as a
        ``customEvents`` row; account / tenant / organization are
        stamped server-side from the gateway headers and JWT.

        Args:
            event_name: Non-empty event name — becomes the App Insights
                row ``name``. The platform redactor runs over this before
                it reaches the sink.
            data: Optional properties flattened into the event. Non-dict
                values are dropped server-side.
            operation_id: Optional correlation id forwarded as the
                ``x-uipath-operation-id`` header. When omitted, falls
                back to :func:`resolve_trace_id` so events emitted from
                the same agent trace share an ``operation_Id`` and are
                queryable together in KQL. When neither is available,
                the header is omitted and App Insights generates its
                own id per event.

        Raises:
            ValueError: If ``event_name`` is empty / whitespace-only, or
                if ``UiPathConfig.organization_id`` /
                ``UiPathConfig.tenant_id`` is not set.
            EnrichedException: If the backend returns a non-2xx response.
        """
        self._validate_event_name(event_name)
        url, headers = self._build_org_scoped_request(LOG_API_PATH)
        resolved_op_id = operation_id or resolve_trace_id()
        if resolved_op_id:
            headers[HEADER_OPERATION_ID] = resolved_op_id
        payload: dict[str, Any] = {"eventName": event_name}
        if data is not None:
            payload["data"] = data
        self.request("POST", url=url, headers=headers, json=payload)

    async def _track_event_async(
        self,
        *,
        event_name: str,
        data: dict[str, Any] | None = None,
        operation_id: str | None = None,
    ) -> None:
        """Async variant of :meth:`_track_event`. Internal seam."""
        self._validate_event_name(event_name)
        url, headers = self._build_org_scoped_request(LOG_API_PATH)
        resolved_op_id = operation_id or resolve_trace_id()
        if resolved_op_id:
            headers[HEADER_OPERATION_ID] = resolved_op_id
        payload: dict[str, Any] = {"eventName": event_name}
        if data is not None:
            payload["data"] = data
        await self.request_async("POST", url=url, headers=headers, json=payload)

    @staticmethod
    def _validate_event_name(event_name: str) -> None:
        """Reject empty/whitespace-only event names client-side.

        The platform's ``/runtime/log`` handler rejects these with a
        4xx; failing fast here gives the caller a clearer error and
        avoids the round trip.
        """
        if not event_name or not event_name.strip():
            raise ValueError("event_name must be a non-empty string.")

    # ── Internals ────────────────────────────────────────────────────

    def _build_org_scoped_request(self, path: str) -> tuple[str, dict[str, str]]:
        """Compose the agenticgovernance_ URL and the tenant header.

        Both governance endpoints share the same URL shape
        (``{origin}/{org_id_uuid}/agenticgovernance_/{path}``) and the
        same ``x-uipath-internal-tenantid`` header — neither matches
        ``UiPathUrl.scope_url`` (slug-based), so the URL is composed
        directly here.

        Honors ``UIPATH_SERVICE_URL_AGENTICGOVERNANCE`` for local dev:
        when set, redirects to the override and injects routing headers
        so the local server sees what the platform router would have
        carried. ``BaseService.request`` does this same dance for paths
        that fit ``scope_url``; the org-UUID-in-path shape forces us to
        run it ourselves before composing the absolute URL.
        """
        organization_id = UiPathConfig.organization_id
        if not organization_id:
            raise ValueError(
                "Governance call requires UIPATH_ORGANIZATION_ID "
                "to be set in the environment."
            )
        tenant_id = UiPathConfig.tenant_id
        if not tenant_id:
            raise ValueError(
                "Governance call requires UIPATH_TENANT_ID "
                "to be set in the environment."
            )

        override = resolve_service_url(f"{GOVERNANCE_SERVICE_PREFIX}/{path}")
        if override:
            headers: dict[str, str] = {}
            inject_routing_headers(headers)
            return override, headers

        url = (
            f"{self._url.base_url}/{organization_id}/{GOVERNANCE_SERVICE_PREFIX}/{path}"
        )
        return url, {HEADER_INTERNAL_TENANT_ID: tenant_id}

    @staticmethod
    def _policy_params(is_conversational: Optional[bool]) -> dict[str, str]:
        if is_conversational is None:
            return {}
        return {
            AGENT_TYPE_PARAM: "conversational" if is_conversational else "autonomous"
        }

    @staticmethod
    def _build_govern_payload(request: GovernRequest) -> dict[str, Any]:
        """Serialize the request and fill missing job-context from UiPathConfig.

        Auto-fill resolution order for each job-context field: caller
        value > ``UiPathConfig`` (env-var-backed) > omit.

        ``model_dump(exclude_none=True)`` already drops fields the caller
        left ``None``, so key presence — not truthiness — is the right
        "was it supplied?" signal: a caller-supplied empty string is
        still a caller value and must not be overridden by the env.
        """
        payload = request.model_dump(by_alias=True, exclude_none=True)
        for wire_key, config_attr in _JOB_CONTEXT_FIELDS:
            if wire_key in payload:
                continue
            value = getattr(UiPathConfig, config_attr, None)
            if value:
                payload[wire_key] = value
        return payload


# Wire-key → UiPathConfig attribute, for compensation payload auto-fill.
_JOB_CONTEXT_FIELDS: tuple[tuple[str, str], ...] = (
    ("folderKey", "folder_key"),
    ("jobKey", "job_key"),
    ("processKey", "process_uuid"),
    ("referenceId", "agent_id"),
    ("agentVersion", "process_version"),
)
