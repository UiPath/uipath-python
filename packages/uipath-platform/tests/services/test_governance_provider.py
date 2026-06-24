"""Tests for UiPathPlatformGovernanceProvider."""

from __future__ import annotations

import pytest
from pytest_httpx import HTTPXMock
from uipath.core.governance import (
    EnforcementMode,
    FiredRule,
    GovernanceCompensationProvider,
    GovernancePolicyProvider,
    GovernRequest,
    PolicyContext,
)

from uipath.platform import UiPathApiConfig, UiPathExecutionContext
from uipath.platform.governance import (
    GovernanceService,
    UiPathPlatformGovernanceProvider,
)

ORG_ID = "11111111-1111-1111-1111-111111111111"
TENANT_ID = "22222222-2222-2222-2222-222222222222"


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
        data={"prompt": "hello"},
        hook="before_model",
        trace_id="0123456789abcdef0123456789abcdef",
        src_timestamp="2026-06-22T10:00:00Z",
        agent_name="my-agent",
        runtime_id="runtime-1",
    )


@pytest.fixture
def provider(
    config: UiPathApiConfig,
    execution_context: UiPathExecutionContext,
    monkeypatch: pytest.MonkeyPatch,
) -> UiPathPlatformGovernanceProvider:
    monkeypatch.setenv("UIPATH_ORGANIZATION_ID", ORG_ID)
    monkeypatch.setenv("UIPATH_TENANT_ID", TENANT_ID)
    service = GovernanceService(config=config, execution_context=execution_context)
    return UiPathPlatformGovernanceProvider(service=service)


class TestConstruction:
    def test_accepts_existing_service(
        self,
        config: UiPathApiConfig,
        execution_context: UiPathExecutionContext,
    ) -> None:
        service = GovernanceService(config=config, execution_context=execution_context)
        provider = UiPathPlatformGovernanceProvider(service=service)
        assert provider.service is service

    def test_builds_service_from_config(
        self,
        config: UiPathApiConfig,
        execution_context: UiPathExecutionContext,
    ) -> None:
        provider = UiPathPlatformGovernanceProvider(
            config=config, execution_context=execution_context
        )
        assert isinstance(provider.service, GovernanceService)

    def test_requires_service_or_full_kwargs(self) -> None:
        with pytest.raises(ValueError, match="GovernanceService"):
            UiPathPlatformGovernanceProvider()


class TestProtocolConformance:
    def test_satisfies_policy_provider_protocol(
        self, provider: UiPathPlatformGovernanceProvider
    ) -> None:
        assert isinstance(provider, GovernancePolicyProvider)

    def test_satisfies_compensation_provider_protocol(
        self, provider: UiPathPlatformGovernanceProvider
    ) -> None:
        assert isinstance(provider, GovernanceCompensationProvider)


class TestDelegation:
    def test_get_policy_delegates_to_service(
        self,
        httpx_mock: HTTPXMock,
        provider: UiPathPlatformGovernanceProvider,
        base_url: str,
    ) -> None:
        httpx_mock.add_response(
            url=(
                f"{base_url}/{ORG_ID}/agenticgovernance_/api/v1/runtime/policy"
                "?agentType=conversational"
            ),
            status_code=200,
            json={"mode": "enforce", "policies": "rules: []"},
        )

        response = provider.get_policy(PolicyContext(is_conversational=True))

        assert response.mode is EnforcementMode.ENFORCE
        assert response.policies == "rules: []"

    async def test_get_policy_async_delegates_to_service(
        self,
        httpx_mock: HTTPXMock,
        provider: UiPathPlatformGovernanceProvider,
        base_url: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}/{ORG_ID}/agenticgovernance_/api/v1/runtime/policy",
            status_code=200,
            json={"mode": "audit", "policies": ""},
        )

        response = await provider.get_policy_async(PolicyContext())

        assert response.mode is EnforcementMode.AUDIT

    def test_compensate_delegates_to_service(
        self,
        httpx_mock: HTTPXMock,
        provider: UiPathPlatformGovernanceProvider,
        base_url: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}/{ORG_ID}/agenticgovernance_/api/v1/runtime/govern",
            status_code=200,
            json={},
        )

        provider.compensate(_make_request())

        requests = httpx_mock.get_requests()
        assert len(requests) == 1
        assert requests[0].method == "POST"

    async def test_compensate_async_delegates_to_service(
        self,
        httpx_mock: HTTPXMock,
        provider: UiPathPlatformGovernanceProvider,
        base_url: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}/{ORG_ID}/agenticgovernance_/api/v1/runtime/govern",
            status_code=200,
            json={},
        )

        await provider.compensate_async(_make_request())

        requests = httpx_mock.get_requests()
        assert len(requests) == 1
        assert requests[0].method == "POST"
