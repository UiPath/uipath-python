"""Tests for AutomationOpsService."""

import json

import httpx
import pytest
from pytest_httpx import HTTPXMock

from uipath.platform import UiPathApiConfig, UiPathExecutionContext
from uipath.platform.automation_ops import AutomationOpsService


@pytest.fixture
def service(
    config: UiPathApiConfig,
    execution_context: UiPathExecutionContext,
) -> AutomationOpsService:
    return AutomationOpsService(config=config, execution_context=execution_context)


class TestAutomationOpsService:
    """Test AutomationOpsService functionality."""

    class TestGetDeployedPolicy:
        """Test get_deployed_policy (sync)."""

        def test_returns_policy_dict(
            self,
            httpx_mock: HTTPXMock,
            service: AutomationOpsService,
            base_url: str,
            org: str,
            tenant: str,
        ) -> None:
            expected_policy = {
                "policy-name": "AITL Policy",
                "data": {
                    "container": {"pii-in-flight-agents": True},
                    "pii-entity-table": [],
                },
            }
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/agenthub_/api/policies/deployed-policy",
                status_code=200,
                json=expected_policy,
            )

            result = service.get_deployed_policy()

            assert result == expected_policy

        def test_uses_post_method(
            self,
            httpx_mock: HTTPXMock,
            service: AutomationOpsService,
            base_url: str,
            org: str,
            tenant: str,
        ) -> None:
            captured_request: httpx.Request | None = None

            def capture(request: httpx.Request) -> httpx.Response:
                nonlocal captured_request
                captured_request = request
                return httpx.Response(status_code=200, json={})

            httpx_mock.add_callback(
                method="POST",
                url=f"{base_url}{org}{tenant}/agenthub_/api/policies/deployed-policy",
                callback=capture,
            )

            service.get_deployed_policy()

            assert captured_request is not None
            assert captured_request.method == "POST"

    class TestGetDeployedPolicyAsync:
        """Test get_deployed_policy_async."""

        async def test_returns_policy_dict(
            self,
            httpx_mock: HTTPXMock,
            service: AutomationOpsService,
            base_url: str,
            org: str,
            tenant: str,
        ) -> None:
            expected_policy = {
                "policy-name": "AITL Policy",
                "data": {
                    "container": {"pii-in-flight-agents": False},
                },
            }
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/agenthub_/api/policies/deployed-policy",
                status_code=200,
                json=expected_policy,
            )

            result = await service.get_deployed_policy_async()

            assert result == expected_policy

        async def test_url_is_tenant_scoped(
            self,
            httpx_mock: HTTPXMock,
            service: AutomationOpsService,
            base_url: str,
            org: str,
            tenant: str,
        ) -> None:
            captured_request: httpx.Request | None = None

            def capture(request: httpx.Request) -> httpx.Response:
                nonlocal captured_request
                captured_request = request
                return httpx.Response(status_code=200, json={})

            httpx_mock.add_callback(
                method="POST",
                url=f"{base_url}{org}{tenant}/agenthub_/api/policies/deployed-policy",
                callback=capture,
            )

            await service.get_deployed_policy_async()

            assert captured_request is not None
            # Tenant-scoped: both org and tenant segments appear in the path
            assert org.strip("/") in captured_request.url.path
            assert tenant.strip("/") in captured_request.url.path

        async def test_request_has_no_body(
            self,
            httpx_mock: HTTPXMock,
            service: AutomationOpsService,
            base_url: str,
            org: str,
            tenant: str,
        ) -> None:
            captured_request: httpx.Request | None = None

            def capture(request: httpx.Request) -> httpx.Response:
                nonlocal captured_request
                captured_request = request
                return httpx.Response(status_code=200, json={})

            httpx_mock.add_callback(
                method="POST",
                url=f"{base_url}{org}{tenant}/agenthub_/api/policies/deployed-policy",
                callback=capture,
            )

            await service.get_deployed_policy_async()

            assert captured_request is not None
            # POST with no body — body should be empty (or an empty JSON object)
            body = captured_request.content
            assert body in (b"", b"null") or json.loads(body) in ({}, None)
