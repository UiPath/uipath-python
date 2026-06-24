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
    """

    model_config = ConfigDict(populate_by_name=True)

    validators: list[str] = Field(alias="type")
    rules: list[FiredRule]
    data: dict[str, Any]
    hook: str
    trace_id: str = Field(alias="traceId")
    src_timestamp: str  # wire key is intentionally snake_case
    agent_name: str = Field(alias="agentName")
    runtime_id: str = Field(alias="runtimeId")

    folder_key: str | None = Field(default=None, alias="folderKey")
    job_key: str | None = Field(default=None, alias="jobKey")
    process_key: str | None = Field(default=None, alias="processKey")
    reference_id: str | None = Field(default=None, alias="referenceId")
    agent_version: str | None = Field(default=None, alias="agentVersion")


# ----------------------------------------------------------------------
# Provider protocols
# ----------------------------------------------------------------------


@runtime_checkable
class GovernancePolicyProvider(Protocol):
    """Contract for fetching the governance policy pack.

    Any object exposing a ``get_policy(context) -> PolicyResponse``
    method satisfies this protocol.
    """

    def get_policy(self, context: PolicyContext) -> PolicyResponse:
        """Fetch the policy pack for the active org/tenant."""
        ...


@runtime_checkable
class GovernanceCompensationProvider(Protocol):
    """Contract for firing the compensating ``/runtime/govern`` POST."""

    def compensate(self, request: GovernRequest) -> None:
        """Fire the compensating governance POST. Fire-and-forget."""
        ...
