"""Tests for the governance provider protocols + wire-format models."""

from __future__ import annotations

import pytest

from uipath.core.governance import (
    EnforcementMode,
    FiredRule,
    GovernanceCompensationProvider,
    GovernancePolicyProvider,
    GovernRequest,
    PolicyContext,
    PolicyResponse,
)


class _FakePolicyProvider:
    def __init__(self) -> None:
        self.calls: list[PolicyContext] = []
        self.async_calls: list[PolicyContext] = []

    def get_policy(self, context: PolicyContext) -> PolicyResponse:
        self.calls.append(context)
        return PolicyResponse(mode=EnforcementMode.ENFORCE, policies="rules: []")

    async def get_policy_async(self, context: PolicyContext) -> PolicyResponse:
        self.async_calls.append(context)
        return PolicyResponse(mode=EnforcementMode.ENFORCE, policies="rules: []")


class _FakeCompensationProvider:
    def __init__(self) -> None:
        self.calls: list[GovernRequest] = []

    def compensate(self, request: GovernRequest) -> None:
        self.calls.append(request)


def _make_request() -> GovernRequest:
    return GovernRequest(
        validators=["pii_detection"],
        rules=[
            FiredRule(
                rule_id="ASI-01",
                rule_name="Block PII in flight",
                pack_name="agent-safety",
                validator="pii_detection",
            )
        ],
        data={"prompt": "hi"},
        hook="before_model",
        trace_id="0123456789abcdef0123456789abcdef",
        src_timestamp="2026-06-22T10:00:00Z",
        agent_name="my-agent",
        runtime_id="runtime-1",
    )


class TestPolicyContext:
    def test_defaults(self) -> None:
        ctx = PolicyContext()
        assert ctx.is_conversational is None

    def test_ignores_unknown_fields(self) -> None:
        ctx = PolicyContext.model_validate(
            {"is_conversational": True, "future_selector": "x"}
        )
        assert ctx.is_conversational is True


class TestPolicyResponse:
    def test_defaults(self) -> None:
        response = PolicyResponse()
        assert response.mode is None
        assert response.policies == ""

    @pytest.mark.parametrize(
        ("wire_value", "expected"),
        [
            ("audit", EnforcementMode.AUDIT),
            ("enforce", EnforcementMode.ENFORCE),
            ("disabled", EnforcementMode.DISABLED),
        ],
    )
    def test_parses_known_modes(
        self, wire_value: str, expected: EnforcementMode
    ) -> None:
        response = PolicyResponse.model_validate({"mode": wire_value})
        assert response.mode is expected

    def test_unknown_mode_falls_back_to_none(self) -> None:
        # Forward-compat: a server-added mode the SDK doesn't know about
        # must not break agent startup. Parses as None so the runtime
        # falls back to its safe default rather than raising.
        response = PolicyResponse.model_validate({"mode": "ludicrous"})
        assert response.mode is None


class TestGovernRequest:
    def test_serializes_wire_aliases(self) -> None:
        payload = _make_request().model_dump(by_alias=True, exclude_none=True)
        assert payload["type"] == ["pii_detection"]
        assert payload["traceId"] == "0123456789abcdef0123456789abcdef"
        assert payload["agentName"] == "my-agent"
        assert payload["runtimeId"] == "runtime-1"
        # src_timestamp is intentionally snake_case on the wire.
        assert payload["src_timestamp"] == "2026-06-22T10:00:00Z"
        # Optional job-context fields left None → excluded.
        for absent in (
            "folderKey",
            "jobKey",
            "processKey",
            "referenceId",
            "agentVersion",
        ):
            assert absent not in payload


class TestProtocolConformance:
    """`runtime_checkable` Protocols should accept structurally-matching objects."""

    def test_fake_policy_provider_satisfies_protocol(self) -> None:
        provider = _FakePolicyProvider()
        assert isinstance(provider, GovernancePolicyProvider)

    def test_fake_compensation_provider_satisfies_protocol(self) -> None:
        provider = _FakeCompensationProvider()
        assert isinstance(provider, GovernanceCompensationProvider)

    def test_object_without_methods_rejected(self) -> None:
        class _NotAProvider:
            pass

        assert not isinstance(_NotAProvider(), GovernancePolicyProvider)
        assert not isinstance(_NotAProvider(), GovernanceCompensationProvider)


class TestEndToEndDispatch:
    """Caller passes a provider directly to the consumer (no global registry)."""

    def test_policy_round_trip(self) -> None:
        provider = _FakePolicyProvider()
        response = provider.get_policy(PolicyContext(is_conversational=True))

        assert response.mode is EnforcementMode.ENFORCE
        assert provider.calls == [PolicyContext(is_conversational=True)]

    @pytest.mark.asyncio
    async def test_policy_round_trip_async(self) -> None:
        """The async variant is the preferred entry point for event-loop hosts.

        Hosts running ``await provider.get_policy_async(ctx)`` overlap
        the fetch with the rest of agent setup; the sync ``get_policy``
        path remains for callers outside an event loop.
        """
        provider = _FakePolicyProvider()
        response = await provider.get_policy_async(
            PolicyContext(is_conversational=False)
        )

        assert response.mode is EnforcementMode.ENFORCE
        assert provider.async_calls == [PolicyContext(is_conversational=False)]
        # Sync slot stays untouched — the two entrypoints are independent.
        assert provider.calls == []

    def test_compensation_round_trip(self) -> None:
        provider = _FakeCompensationProvider()
        request = _make_request()
        provider.compensate(request)

        assert provider.calls == [request]
