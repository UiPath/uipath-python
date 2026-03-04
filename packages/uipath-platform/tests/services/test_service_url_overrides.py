import pytest

from uipath.platform.common._service_url_overrides import (
    inject_routing_headers,
    resolve_service_url,
)


class TestResolveServiceUrl:
    def test_returns_none_when_no_override(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("UIPATH_SERVICE_URL_AGENTHUB", raising=False)
        assert resolve_service_url("agenthub_/llm/api/chat/completions") is None

    def test_agenthub_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("UIPATH_SERVICE_URL_AGENTHUB", "http://localhost:5200")
        result = resolve_service_url("agenthub_/llm/api/chat/completions")
        assert result == "http://localhost:5200/llm/api/chat/completions"

    def test_orchestrator_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("UIPATH_SERVICE_URL_ORCHESTRATOR", "http://localhost:8080")
        result = resolve_service_url("orchestrator_/odata/Buckets")
        assert result == "http://localhost:8080/odata/Buckets"

    def test_leading_slash_stripped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("UIPATH_SERVICE_URL_AGENTHUB", "http://localhost:5200")
        result = resolve_service_url("/agenthub_/llm/api/chat/completions")
        assert result == "http://localhost:5200/llm/api/chat/completions"

    def test_trailing_slash_on_override_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("UIPATH_SERVICE_URL_AGENTHUB", "http://localhost:5200/")
        result = resolve_service_url("agenthub_/llm/api/chat/completions")
        assert result == "http://localhost:5200/llm/api/chat/completions"

    def test_compound_service_prefix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("UIPATH_SERVICE_URL_AGENTSRUNTIME", "http://localhost:6100")
        result = resolve_service_url("agentsruntime_/api/execution/guardrails/validate")
        assert result == "http://localhost:6100/api/execution/guardrails/validate"

    def test_no_service_prefix_returns_none(self) -> None:
        assert resolve_service_url("api/v1/users") is None

    def test_empty_path_returns_none(self) -> None:
        assert resolve_service_url("") is None

    def test_service_only_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("UIPATH_SERVICE_URL_AGENTHUB", "http://localhost:5200")
        result = resolve_service_url("agenthub_/")
        assert result == "http://localhost:5200/"

    def test_query_params_preserved(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("UIPATH_SERVICE_URL_AGENTHUB", "http://localhost:5200")
        result = resolve_service_url(
            "agenthub_/llm/openai/deployments/gpt-4/chat/completions?api-version=2024-10-21"
        )
        assert (
            result
            == "http://localhost:5200/llm/openai/deployments/gpt-4/chat/completions?api-version=2024-10-21"
        )


class TestInjectRoutingHeaders:
    def test_injects_tenant_and_org(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("UIPATH_TENANT_ID", "tenant-123")
        monkeypatch.setenv("UIPATH_ORGANIZATION_ID", "org-456")
        headers: dict[str, str] = {}
        inject_routing_headers(headers)
        assert headers["X-UiPath-Internal-TenantId"] == "tenant-123"
        assert headers["X-UiPath-Internal-AccountId"] == "org-456"

    def test_skips_missing_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("UIPATH_TENANT_ID", raising=False)
        monkeypatch.delenv("UIPATH_ORGANIZATION_ID", raising=False)
        headers: dict[str, str] = {}
        inject_routing_headers(headers)
        assert "X-UiPath-Internal-TenantId" not in headers
        assert "X-UiPath-Internal-AccountId" not in headers

    def test_does_not_overwrite_existing_headers(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("UIPATH_TENANT_ID", "tenant-123")
        monkeypatch.setenv("UIPATH_ORGANIZATION_ID", "org-456")
        headers: dict[str, str] = {"X-Custom": "keep-me"}
        inject_routing_headers(headers)
        assert headers["X-Custom"] == "keep-me"
        assert headers["X-UiPath-Internal-TenantId"] == "tenant-123"
