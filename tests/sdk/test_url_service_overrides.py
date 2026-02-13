"""Integration tests for UiPathUrl.scope_url() with service URL overrides."""

from typing import TYPE_CHECKING

from uipath._utils._service_url_overrides import clear_overrides_cache
from uipath._utils._url import UiPathUrl

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


class TestScopeUrlWithOverrides:
    """Tests for scope_url() interacting with service URL overrides."""

    def setup_method(self) -> None:
        clear_overrides_cache()

    def teardown_method(self) -> None:
        clear_overrides_cache()

    def _make_url(self) -> UiPathUrl:
        return UiPathUrl("https://cloud.uipath.com/myorg/mytenant")

    def test_no_override_unchanged(self) -> None:
        """Standard scoping is preserved when no override is set."""
        url = self._make_url()
        result = url.scope_url("/orchestrator_/odata/Jobs")
        assert result == "myorg/mytenant/orchestrator_/odata/Jobs"

    def test_localhost_override_strips_prefix(self, monkeypatch: "MonkeyPatch") -> None:
        """Service prefix is stripped and request routes to localhost."""
        monkeypatch.setenv("UIPATH_ORCHESTRATOR_URL", "http://localhost:8080")
        url = self._make_url()
        result = url.scope_url("/orchestrator_/odata/Jobs")
        assert result == "http://localhost:8080/odata/Jobs"

    def test_remote_override_strips_prefix(self, monkeypatch: "MonkeyPatch") -> None:
        """Prefix stripping works for non-localhost override URLs too."""
        monkeypatch.setenv("UIPATH_AGENTHUB_URL", "https://dev.internal.example.com")
        url = self._make_url()
        result = url.scope_url("/agenthub_/api/v1/agents")
        assert result == "https://dev.internal.example.com/api/v1/agents"

    def test_absolute_url_not_intercepted(self, monkeypatch: "MonkeyPatch") -> None:
        """Already-absolute URLs pass through without override check."""
        monkeypatch.setenv("UIPATH_ORCHESTRATOR_URL", "http://localhost:8080")
        url = self._make_url()
        result = url.scope_url("https://other.host/orchestrator_/odata/Jobs")
        assert result == "https://other.host/orchestrator_/odata/Jobs"

    def test_non_service_url_unchanged(self, monkeypatch: "MonkeyPatch") -> None:
        """Paths without a service prefix (trailing _) are not intercepted."""
        monkeypatch.setenv("UIPATH_ORCHESTRATOR_URL", "http://localhost:8080")
        url = self._make_url()
        # "api" doesn't end with _ so it should follow normal scoping
        result = url.scope_url("/api/v1/status")
        assert result == "myorg/mytenant/api/v1/status"

    def test_multiple_services_independent(self, monkeypatch: "MonkeyPatch") -> None:
        """Only configured services are overridden; others scope normally."""
        monkeypatch.setenv("UIPATH_ORCHESTRATOR_URL", "http://localhost:8080")
        url = self._make_url()

        # Overridden service
        assert (
            url.scope_url("/orchestrator_/odata/Jobs")
            == "http://localhost:8080/odata/Jobs"
        )
        # Non-overridden service follows normal scoping
        assert (
            url.scope_url("/agenthub_/api/v1/agents")
            == "myorg/mytenant/agenthub_/api/v1/agents"
        )

    def test_override_prefix_only_path(self, monkeypatch: "MonkeyPatch") -> None:
        """URL consisting of only the service prefix returns just the base."""
        monkeypatch.setenv("UIPATH_ORCHESTRATOR_URL", "http://localhost:8080")
        url = self._make_url()
        result = url.scope_url("/orchestrator_/")
        assert result == "http://localhost:8080"
