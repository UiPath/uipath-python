"""Provider protocols for governance backend interactions.

The runtime needs two backend interactions to function:

- Fetching the policy pack at startup.
- Firing the compensating ``/runtime/govern`` POST when a
  ``guardrail_fallback`` rule matches so the server can run the disabled
  centralised guardrail and write the per-rule LLMOps audit records.

Both have wire formats owned by the ``agenticgovernance_`` ingress.
Defining the contracts here — alongside :class:`EvaluatorProtocol` —
lets runtime consumers depend on stable protocols and receive a
concrete provider via constructor injection. Concrete providers live
outside this package; ``uipath-core`` does not import them.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import EnforcementMode

# ----------------------------------------------------------------------
# Wire-format models
# ----------------------------------------------------------------------


class PolicyContext(BaseModel):
    """Caller-supplied selectors for the policy fetch.

    Wrapping the selectors in a model keeps the protocol surface stable
    when the server grows new selector dimensions — adding a field here
    doesn't change :meth:`GovernancePolicyProvider.get_policy`.

    Today carries only :attr:`is_conversational`; future selectors land
    here.
    """

    model_config = ConfigDict(extra="ignore")

    is_conversational: bool | None = None


class PolicyResponse(BaseModel):
    """Parsed governance backend response.

    Wire envelope::

        {
            "mode": "audit" | "enforce" | "disabled",
            "policies": "<YAML string>"
        }

    Attributes:
        mode: Platform-controlled enforcement mode for the tenant. May
            be ``None`` when the backend omits it. A wire value the SDK
            doesn't know about parses as ``None`` rather than raising,
            so a server-side mode addition can't break agent startup.
        policies: Policy pack YAML the caller compiles into its policy
            index. May be an empty string when no rules are configured.
    """

    model_config = ConfigDict(extra="ignore")

    mode: EnforcementMode | None = Field(default=None)
    policies: str = Field(default="")

    @field_validator("mode", mode="before")
    @classmethod
    def _coerce_mode(cls, value: object) -> EnforcementMode | None:
        if value is None or isinstance(value, EnforcementMode):
            return value
        try:
            return EnforcementMode(value)
        except ValueError:
            return None


class HookBundle(BaseModel):
    """Metadata for one hook's WASM policy bundle.

    Returned as an element of :class:`AllPoliciesResponse` from the
    ``/all-policies/{tenant_id}`` endpoint.

    Attributes:
        hook_type: Lifecycle hook identifier (e.g. ``"before_agent"``).
        bundle_url: Pre-signed URL for the WASM ``.tar.gz`` bundle.
            No platform auth required — the URL carries its own credentials.
        etag: Server-assigned ETag for the bundle. Used by the Rego loader
            to skip unchanged bundles on background refresh. ``None`` when
            the server does not provide one.
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    hook_type: str = Field(alias="hookType")
    bundle_url: str = Field(alias="bundleUrl")
    etag: str | None = Field(default=None)


class AllPoliciesResponse(BaseModel):
    """Parsed response from the ``/all-policies/{tenant_id}`` endpoint.

    Wire envelope::

        {
            "hookBundles": [
                {
                    "hookType": "before_agent",
                    "bundleUrl": "https://url.example.com/...",
                    "etag": "abc123"
                }
            ]
        }

    Attributes:
        hook_bundles: One entry per lifecycle hook that has a compiled
            WASM bundle. Empty when no policies are configured for the
            tenant.
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    hook_bundles: list[HookBundle] = Field(default_factory=list, alias="hookBundles")


class FiredRule(BaseModel):
    """Per-rule metadata carried in the ``/runtime/govern`` payload.

    One entry per matching ``guardrail_fallback`` condition. The server
    writes one LLMOps trace record per entry, so callers must include
    every fired rule even when multiple share the same ``validator``.
    """

    model_config = ConfigDict(populate_by_name=True)

    rule_id: str = Field(alias="ruleId")
    rule_name: str = Field(alias="ruleName")
    pack_name: str = Field(alias="packName")
    validator: str


class GovernRequest(BaseModel):
    """Request body for the ``/runtime/govern`` compensating governance POST.

    Field aliases match the on-the-wire JSON keys. ``src_timestamp`` is
    snake_case on the wire (intentional — preserved verbatim); every
    other key is camelCase.

    Job-context fields (``folder_key`` / ``job_key`` / ``process_key`` /
    ``reference_id`` / ``agent_version``) are optional; callers omit
    them by leaving them ``None``. How unset fields are resolved (e.g.
    auto-filled from environment) is the concrete provider's concern,
    not part of this wire contract.

    ``trace_id`` is optional. When ``None`` the field is omitted from
    the wire JSON (via ``exclude_none=True`` at serialisation). Whether
    a concrete provider chooses to populate a missing value before
    sending is the provider's concern, not part of this contract.
    """

    model_config = ConfigDict(populate_by_name=True)

    validators: list[str] = Field(alias="type")
    rules: list[FiredRule]
    data: dict[str, Any]
    hook: str
    trace_id: str | None = Field(default=None, alias="traceId")
    src_timestamp: str  # wire key is intentionally snake_case
    agent_name: str = Field(alias="agentName")
    runtime_id: str = Field(alias="runtimeId")

    folder_key: str | None = Field(default=None, alias="folderKey")
    job_key: str | None = Field(default=None, alias="jobKey")
    process_key: str | None = Field(default=None, alias="processKey")
    reference_id: str | None = Field(default=None, alias="referenceId")
    agent_version: str | None = Field(default=None, alias="agentVersion")

    # Runtime identity for governance telemetry; the server stamps these on the
    # rule-denied events it emits. Optional — omitted from the wire when None.
    agent_framework: str | None = Field(default=None, alias="agentFramework")
    agent_type: str | None = Field(default=None, alias="agentType")
    runtime_version: str | None = Field(default=None, alias="runtimeVersion")


# ----------------------------------------------------------------------
# Provider protocols
# ----------------------------------------------------------------------


@runtime_checkable
class GovernancePolicyProvider(Protocol):
    """Contract for fetching the governance policy pack.

    Implementations expose both a sync and an async fetch. The async
    variant is the preferred entry point for hosts running on an event
    loop (the host can overlap policy fetch with the rest of agent
    setup via ``asyncio.create_task`` and ``await`` the resolved
    :class:`PolicyResponse` before constructing the governance
    wrapper). The sync variant is kept for callers outside an event
    loop (CLI tools, integration tests).

    Any object exposing both ``get_policy(context) -> PolicyResponse``
    and ``async def get_policy_async(context) -> PolicyResponse``
    satisfies this protocol.
    """

    def get_policy(self, context: PolicyContext) -> PolicyResponse:
        """Fetch the policy pack for the active org/tenant."""
        ...

    async def get_policy_async(self, context: PolicyContext) -> PolicyResponse:
        """Async variant of :meth:`get_policy`.

        Hosts running on an event loop should use this so the fetch
        doesn't block the loop and can overlap with other startup
        work.
        """
        ...


@runtime_checkable
class GovernanceCompensationProvider(Protocol):
    """Contract for firing the compensating ``/runtime/govern`` POST."""

    def compensate(self, request: GovernRequest) -> None:
        """Fire the compensating governance POST. Fire-and-forget."""
        ...
