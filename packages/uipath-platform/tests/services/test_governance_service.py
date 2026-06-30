"""Tests for GovernanceService."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from pytest_httpx import HTTPXMock
from uipath.core.governance import GovernancePolicyProvider, PolicyContext

from uipath.platform import UiPathApiConfig, UiPathExecutionContext
from uipath.platform.common import resolve_trace_id
from uipath.platform.governance import (
    FiredRule,
    GovernanceService,
    PolicyResponse,
)

ORG_ID = "11111111-1111-1111-1111-111111111111"
TENANT_ID = "22222222-2222-2222-2222-222222222222"
TENANT_ID_HEX = TENANT_ID.replace("-", "").lower()


def _compensate_kwargs(**overrides: Any) -> dict[str, Any]:
    """Default kwargs for ``service.compensate(...)``."""
    defaults: dict[str, Any] = dict(
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
    defaults.update(overrides)
    return defaults


@pytest.fixture
def service(
    config: UiPathApiConfig,
    execution_context: UiPathExecutionContext,
    monkeypatch: pytest.MonkeyPatch,
) -> GovernanceService:
    monkeypatch.setenv("UIPATH_ORGANIZATION_ID", ORG_ID)
    monkeypatch.setenv("UIPATH_TENANT_ID", TENANT_ID)
    return GovernanceService(config=config, execution_context=execution_context)


class TestGovernanceService:
    """Test GovernanceService functionality."""

    class TestRetrievePolicy:
        """Test retrieve_policy (sync)."""

        def test_returns_parsed_policy(
            self,
            httpx_mock: HTTPXMock,
            service: GovernanceService,
            base_url: str,
        ) -> None:
            httpx_mock.add_response(
                url=f"{base_url}/{ORG_ID}/agenticgovernance_/api/v1/runtime/policy",
                status_code=200,
                json={"mode": "enforce", "policies": "rules: []"},
            )

            result = service.retrieve_policy()

            assert isinstance(result, PolicyResponse)
            assert result.mode == "enforce"
            assert result.policies == "rules: []"

        def test_defaults_when_fields_missing(
            self,
            httpx_mock: HTTPXMock,
            service: GovernanceService,
            base_url: str,
        ) -> None:
            httpx_mock.add_response(
                url=f"{base_url}/{ORG_ID}/agenticgovernance_/api/v1/runtime/policy",
                status_code=200,
                json={},
            )

            result = service.retrieve_policy()

            assert result.mode is None
            assert result.policies == ""

        def test_sends_tenant_header_and_bearer_token(
            self,
            httpx_mock: HTTPXMock,
            service: GovernanceService,
            base_url: str,
            secret: str,
        ) -> None:
            captured: dict[str, httpx.Request] = {}

            def capture(request: httpx.Request) -> httpx.Response:
                captured["request"] = request
                return httpx.Response(200, json={"mode": "audit", "policies": ""})

            httpx_mock.add_callback(
                capture,
                url=f"{base_url}/{ORG_ID}/agenticgovernance_/api/v1/runtime/policy",
            )

            service.retrieve_policy()

            request = captured["request"]
            assert request.method == "GET"
            assert request.headers["x-uipath-internal-tenantid"] == TENANT_ID
            assert request.headers["authorization"] == f"Bearer {secret}"
            # No agentType query param when caller omits it.
            assert "agentType" not in request.url.params

        @pytest.mark.parametrize(
            ("is_conversational", "expected"),
            [(True, "conversational"), (False, "autonomous")],
        )
        def test_appends_agent_type_query_param(
            self,
            httpx_mock: HTTPXMock,
            service: GovernanceService,
            base_url: str,
            is_conversational: bool,
            expected: str,
        ) -> None:
            captured: dict[str, httpx.Request] = {}

            def capture(request: httpx.Request) -> httpx.Response:
                captured["request"] = request
                return httpx.Response(200, json={"mode": "audit", "policies": ""})

            httpx_mock.add_callback(
                capture,
                url=(
                    f"{base_url}/{ORG_ID}/agenticgovernance_/api/v1/runtime/policy"
                    f"?agentType={expected}"
                ),
            )

            service.retrieve_policy(is_conversational=is_conversational)

            assert captured["request"].url.params["agentType"] == expected

        def test_raises_when_organization_id_missing(
            self,
            config: UiPathApiConfig,
            execution_context: UiPathExecutionContext,
            monkeypatch: pytest.MonkeyPatch,
        ) -> None:
            monkeypatch.delenv("UIPATH_ORGANIZATION_ID", raising=False)
            monkeypatch.setenv("UIPATH_TENANT_ID", TENANT_ID)
            service = GovernanceService(
                config=config, execution_context=execution_context
            )

            with pytest.raises(ValueError, match="UIPATH_ORGANIZATION_ID"):
                service.retrieve_policy()

        def test_raises_when_tenant_id_missing(
            self,
            config: UiPathApiConfig,
            execution_context: UiPathExecutionContext,
            monkeypatch: pytest.MonkeyPatch,
        ) -> None:
            monkeypatch.setenv("UIPATH_ORGANIZATION_ID", ORG_ID)
            monkeypatch.delenv("UIPATH_TENANT_ID", raising=False)
            service = GovernanceService(
                config=config, execution_context=execution_context
            )

            with pytest.raises(ValueError, match="UIPATH_TENANT_ID"):
                service.retrieve_policy()

        def test_raises_on_http_error(
            self,
            httpx_mock: HTTPXMock,
            service: GovernanceService,
            base_url: str,
        ) -> None:
            from uipath.platform.errors import EnrichedException

            httpx_mock.add_response(
                url=f"{base_url}/{ORG_ID}/agenticgovernance_/api/v1/runtime/policy",
                status_code=500,
                text="boom",
            )

            with pytest.raises(EnrichedException):
                service.retrieve_policy()

    class TestRetrievePolicyAsync:
        """Test retrieve_policy_async."""

        async def test_returns_parsed_policy(
            self,
            httpx_mock: HTTPXMock,
            service: GovernanceService,
            base_url: str,
        ) -> None:
            httpx_mock.add_response(
                url=(
                    f"{base_url}/{ORG_ID}/agenticgovernance_/api/v1/runtime/policy"
                    "?agentType=autonomous"
                ),
                status_code=200,
                json={"mode": "audit", "policies": "rules: []"},
            )

            result = await service.retrieve_policy_async(is_conversational=False)

            assert result.mode == "audit"
            assert result.policies == "rules: []"

    class TestCompensate:
        """Test compensate (sync)."""

        def test_posts_aliased_payload(
            self,
            httpx_mock: HTTPXMock,
            service: GovernanceService,
            base_url: str,
            secret: str,
        ) -> None:
            captured: dict[str, httpx.Request] = {}

            def capture(request: httpx.Request) -> httpx.Response:
                captured["request"] = request
                return httpx.Response(200, json={})

            httpx_mock.add_callback(
                capture,
                url=f"{base_url}/{ORG_ID}/agenticgovernance_/api/v1/runtime/govern",
            )

            service.compensate(**_compensate_kwargs())

            request = captured["request"]
            assert request.method == "POST"
            assert request.headers["x-uipath-internal-tenantid"] == TENANT_ID
            assert request.headers["authorization"] == f"Bearer {secret}"

            body = json.loads(request.content)
            assert body["type"] == ["pii_detection"]
            assert body["rules"] == [
                {
                    "ruleId": "ASI-01",
                    "ruleName": "Block PII in flight",
                    "packName": "agent-safety",
                    "validator": "pii_detection",
                }
            ]
            assert body["traceId"] == "0123456789abcdef0123456789abcdef"
            assert body["src_timestamp"] == "2026-06-22T10:00:00Z"
            assert body["agentName"] == "my-agent"
            assert body["runtimeId"] == "runtime-1"
            assert body["hook"] == "before_model"
            assert body["data"] == {"prompt": "hello"}

        def test_autofills_job_context_from_config(
            self,
            httpx_mock: HTTPXMock,
            service: GovernanceService,
            base_url: str,
            monkeypatch: pytest.MonkeyPatch,
        ) -> None:
            monkeypatch.setenv("UIPATH_FOLDER_KEY", "folder-from-env")
            monkeypatch.setenv("UIPATH_JOB_KEY", "job-from-env")
            monkeypatch.setenv("UIPATH_PROCESS_UUID", "process-from-env")
            monkeypatch.setenv("UIPATH_AGENT_ID", "agent-from-env")
            monkeypatch.setenv("UIPATH_PROCESS_VERSION", "1.2.3")

            captured: dict[str, httpx.Request] = {}

            def capture(request: httpx.Request) -> httpx.Response:
                captured["request"] = request
                return httpx.Response(200, json={})

            httpx_mock.add_callback(
                capture,
                url=f"{base_url}/{ORG_ID}/agenticgovernance_/api/v1/runtime/govern",
            )

            service.compensate(**_compensate_kwargs())

            body = json.loads(captured["request"].content)
            assert body["folderKey"] == "folder-from-env"
            assert body["jobKey"] == "job-from-env"
            assert body["processKey"] == "process-from-env"
            assert body["referenceId"] == "agent-from-env"
            assert body["agentVersion"] == "1.2.3"

        def test_caller_overrides_take_precedence(
            self,
            httpx_mock: HTTPXMock,
            service: GovernanceService,
            base_url: str,
            monkeypatch: pytest.MonkeyPatch,
        ) -> None:
            monkeypatch.setenv("UIPATH_FOLDER_KEY", "env-folder")
            monkeypatch.setenv("UIPATH_JOB_KEY", "env-job")

            captured: dict[str, httpx.Request] = {}

            def capture(request: httpx.Request) -> httpx.Response:
                captured["request"] = request
                return httpx.Response(200, json={})

            httpx_mock.add_callback(
                capture,
                url=f"{base_url}/{ORG_ID}/agenticgovernance_/api/v1/runtime/govern",
            )

            service.compensate(**_compensate_kwargs(folder_key="explicit-folder"))

            body = json.loads(captured["request"].content)
            # Caller-supplied value wins.
            assert body["folderKey"] == "explicit-folder"
            # Env-backed fallback fills the unset one.
            assert body["jobKey"] == "env-job"
            # Unset and unbacked → key omitted.
            assert "processKey" not in body

        def test_caller_empty_string_is_not_overridden_by_env(
            self,
            httpx_mock: HTTPXMock,
            service: GovernanceService,
            base_url: str,
            monkeypatch: pytest.MonkeyPatch,
        ) -> None:
            monkeypatch.setenv("UIPATH_FOLDER_KEY", "env-folder")

            captured: dict[str, httpx.Request] = {}

            def capture(request: httpx.Request) -> httpx.Response:
                captured["request"] = request
                return httpx.Response(200, json={})

            httpx_mock.add_callback(
                capture,
                url=f"{base_url}/{ORG_ID}/agenticgovernance_/api/v1/runtime/govern",
            )

            # Explicit empty string is still a caller value — must not be
            # silently replaced by the env-backed UiPathConfig fallback.
            service.compensate(**_compensate_kwargs(folder_key=""))

            body = json.loads(captured["request"].content)
            assert body["folderKey"] == ""

        def test_omits_job_context_keys_with_no_value(
            self,
            httpx_mock: HTTPXMock,
            service: GovernanceService,
            base_url: str,
            monkeypatch: pytest.MonkeyPatch,
        ) -> None:
            for env_key in (
                "UIPATH_FOLDER_KEY",
                "UIPATH_JOB_KEY",
                "UIPATH_PROCESS_UUID",
                "UIPATH_AGENT_ID",
                "UIPATH_PROCESS_VERSION",
                "UIPATH_PROJECT_ID",
            ):
                monkeypatch.delenv(env_key, raising=False)

            captured: dict[str, httpx.Request] = {}

            def capture(request: httpx.Request) -> httpx.Response:
                captured["request"] = request
                return httpx.Response(200, json={})

            httpx_mock.add_callback(
                capture,
                url=f"{base_url}/{ORG_ID}/agenticgovernance_/api/v1/runtime/govern",
            )

            service.compensate(**_compensate_kwargs())

            body = json.loads(captured["request"].content)
            for absent in (
                "folderKey",
                "jobKey",
                "processKey",
                "referenceId",
                "agentVersion",
            ):
                assert absent not in body

        def test_raises_on_http_error(
            self,
            httpx_mock: HTTPXMock,
            service: GovernanceService,
            base_url: str,
        ) -> None:
            from uipath.platform.errors import EnrichedException

            httpx_mock.add_response(
                url=f"{base_url}/{ORG_ID}/agenticgovernance_/api/v1/runtime/govern",
                status_code=400,
                text="bad payload",
            )

            with pytest.raises(EnrichedException):
                service.compensate(**_compensate_kwargs())

        def test_raises_when_org_id_missing(
            self,
            config: UiPathApiConfig,
            execution_context: UiPathExecutionContext,
            monkeypatch: pytest.MonkeyPatch,
        ) -> None:
            monkeypatch.delenv("UIPATH_ORGANIZATION_ID", raising=False)
            monkeypatch.setenv("UIPATH_TENANT_ID", TENANT_ID)
            service = GovernanceService(
                config=config, execution_context=execution_context
            )

            with pytest.raises(ValueError, match="UIPATH_ORGANIZATION_ID"):
                service.compensate(**_compensate_kwargs())

        def test_self_resolves_trace_id_when_caller_leaves_none(
            self,
            httpx_mock: HTTPXMock,
            service: GovernanceService,
            base_url: str,
            monkeypatch: pytest.MonkeyPatch,
        ) -> None:
            """``trace_id=None`` from the caller is filled via resolve_trace_id().

            The runtime layer intentionally stays env-free; the platform
            service fills the canonical trace id at HTTP-call time from
            the OTel/env source. ``UIPATH_TRACE_ID`` covers the
            resolver-finds-a-value branch of ``_resolve_request_trace_id``.
            """
            monkeypatch.setenv("UIPATH_TRACE_ID", TENANT_ID_HEX)
            captured: dict[str, httpx.Request] = {}

            def capture(request: httpx.Request) -> httpx.Response:
                captured["request"] = request
                return httpx.Response(200, json={})

            httpx_mock.add_callback(
                capture,
                url=f"{base_url}/{ORG_ID}/agenticgovernance_/api/v1/runtime/govern",
            )

            service.compensate(**_compensate_kwargs(trace_id=None))

            body = json.loads(captured["request"].content)
            assert body["traceId"] == TENANT_ID_HEX

        def test_omits_trace_id_when_no_source_resolves(
            self,
            httpx_mock: HTTPXMock,
            service: GovernanceService,
            base_url: str,
            monkeypatch: pytest.MonkeyPatch,
        ) -> None:
            """Resolver returns nothing → traceId is omitted from the body.

            Covers the resolver-finds-nothing branch of
            ``_resolve_request_trace_id``: no ``UIPATH_TRACE_ID``, no
            active OTel context → ``trace_id`` stays ``None`` on the
            request and ``model_dump(exclude_none=True)`` drops it from
            the wire JSON.
            """
            monkeypatch.delenv("UIPATH_TRACE_ID", raising=False)
            captured: dict[str, httpx.Request] = {}

            def capture(request: httpx.Request) -> httpx.Response:
                captured["request"] = request
                return httpx.Response(200, json={})

            httpx_mock.add_callback(
                capture,
                url=f"{base_url}/{ORG_ID}/agenticgovernance_/api/v1/runtime/govern",
            )

            service.compensate(**_compensate_kwargs(trace_id=None))

            body = json.loads(captured["request"].content)
            assert "traceId" not in body

        def test_caller_empty_string_wins_over_resolver(
            self,
            httpx_mock: HTTPXMock,
            service: GovernanceService,
            base_url: str,
            monkeypatch: pytest.MonkeyPatch,
        ) -> None:
            """An explicit ``trace_id=""`` from the caller is not overridden.

            With the absence-via-``None`` contract, the empty string is
            a legitimate caller-supplied value — it must not trigger
            the auto-resolve.
            """
            monkeypatch.setenv("UIPATH_TRACE_ID", TENANT_ID_HEX)
            captured: dict[str, httpx.Request] = {}

            def capture(request: httpx.Request) -> httpx.Response:
                captured["request"] = request
                return httpx.Response(200, json={})

            httpx_mock.add_callback(
                capture,
                url=f"{base_url}/{ORG_ID}/agenticgovernance_/api/v1/runtime/govern",
            )

            service.compensate(**_compensate_kwargs(trace_id=""))

            body = json.loads(captured["request"].content)
            assert body["traceId"] == ""

    class TestCompensateAsync:
        """Test compensate_async."""

        async def test_posts_aliased_payload(
            self,
            httpx_mock: HTTPXMock,
            service: GovernanceService,
            base_url: str,
        ) -> None:
            httpx_mock.add_response(
                url=f"{base_url}/{ORG_ID}/agenticgovernance_/api/v1/runtime/govern",
                status_code=200,
                json={},
            )

            await service.compensate_async(**_compensate_kwargs())

            requests = httpx_mock.get_requests()
            assert len(requests) == 1
            assert requests[0].method == "POST"

    class TestProtocolConformance:
        """``get_policy`` adapter is the only protocol-shaped surface left
        on :class:`GovernanceService`; compensation conformance is tested
        against :class:`UiPathPlatformGovernanceProvider`.
        """

        def test_satisfies_policy_provider_protocol(
            self, service: GovernanceService
        ) -> None:
            assert isinstance(service, GovernancePolicyProvider)

        def test_get_policy_delegates_to_retrieve_policy(
            self,
            httpx_mock: HTTPXMock,
            service: GovernanceService,
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

            response = service.get_policy(PolicyContext(is_conversational=True))

            assert response.mode == "enforce"
            assert response.policies == "rules: []"

        async def test_get_policy_async_delegates(
            self,
            httpx_mock: HTTPXMock,
            service: GovernanceService,
            base_url: str,
        ) -> None:
            httpx_mock.add_response(
                url=f"{base_url}/{ORG_ID}/agenticgovernance_/api/v1/runtime/policy",
                status_code=200,
                json={"mode": "audit", "policies": ""},
            )

            response = await service.get_policy_async(PolicyContext())

            assert response.mode == "audit"

    class TestServiceUrlOverride:
        """Honor UIPATH_SERVICE_URL_AGENTICGOVERNANCE for local dev."""

        def test_redirects_policy_fetch_to_override(
            self,
            httpx_mock: HTTPXMock,
            service: GovernanceService,
            monkeypatch: pytest.MonkeyPatch,
        ) -> None:
            monkeypatch.setenv(
                "UIPATH_SERVICE_URL_AGENTICGOVERNANCE", "http://localhost:8123"
            )
            captured: dict[str, httpx.Request] = {}

            def capture(request: httpx.Request) -> httpx.Response:
                captured["request"] = request
                return httpx.Response(200, json={"mode": "audit", "policies": ""})

            httpx_mock.add_callback(
                capture, url="http://localhost:8123/api/v1/runtime/policy"
            )

            service.retrieve_policy()

            request = captured["request"]
            # Routing headers replace the platform router, org-UUID path is dropped.
            assert request.headers["X-UiPath-Internal-TenantId"] == TENANT_ID
            assert request.headers["X-UiPath-Internal-AccountId"] == ORG_ID
            assert ORG_ID not in str(request.url)

        def test_redirects_compensate_to_override(
            self,
            httpx_mock: HTTPXMock,
            service: GovernanceService,
            monkeypatch: pytest.MonkeyPatch,
        ) -> None:
            monkeypatch.setenv(
                "UIPATH_SERVICE_URL_AGENTICGOVERNANCE", "http://localhost:8123"
            )
            httpx_mock.add_response(
                url="http://localhost:8123/api/v1/runtime/govern",
                method="POST",
                status_code=200,
                json={},
            )

            service.compensate(**_compensate_kwargs())

            sent = httpx_mock.get_requests()[-1]
            assert sent.method == "POST"
            assert sent.headers["X-UiPath-Internal-AccountId"] == ORG_ID


class TestResolveTraceId:
    """Test the resolve_trace_id helper."""

    def test_returns_fallback_when_no_source_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("UIPATH_TRACE_ID", raising=False)

        assert resolve_trace_id(fallback="fallback-id") == "fallback-id"

    def test_returns_none_when_no_fallback(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("UIPATH_TRACE_ID", raising=False)

        assert resolve_trace_id() is None

    def test_reads_uipath_trace_id_in_hex_form(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("UIPATH_TRACE_ID", "0123456789abcdef0123456789abcdef")

        assert resolve_trace_id() == "0123456789abcdef0123456789abcdef"

    def test_normalizes_uipath_trace_id_in_uuid_form(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("UIPATH_TRACE_ID", TENANT_ID)

        assert resolve_trace_id() == TENANT_ID_HEX

    def test_falls_through_when_uipath_trace_id_is_malformed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("UIPATH_TRACE_ID", "not-a-valid-trace-id")

        # No OTel context active → falls through to caller-supplied fallback.
        assert resolve_trace_id(fallback="recovered") == "recovered"
