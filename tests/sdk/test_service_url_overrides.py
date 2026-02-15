"""Tests for service URL override resolution module."""

from typing import TYPE_CHECKING

from uipath._utils._service_url_overrides import (
    clear_overrides_cache,
    get_service_override,
)

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


class TestGetServiceOverride:
    """Tests for get_service_override()."""

    def setup_method(self) -> None:
        clear_overrides_cache()

    def teardown_method(self) -> None:
        clear_overrides_cache()

    def test_no_override_returns_none(self, monkeypatch: "MonkeyPatch") -> None:
        """Returns None when no env var is set."""
        monkeypatch.delenv("UIPATH_ORCHESTRATOR_URL", raising=False)
        assert get_service_override("orchestrator_") is None

    def test_orchestrator_override(self, monkeypatch: "MonkeyPatch") -> None:
        """Returns the override URL for orchestrator."""
        monkeypatch.setenv("UIPATH_ORCHESTRATOR_URL", "http://localhost:8080")
        assert get_service_override("orchestrator_") == "http://localhost:8080"

    def test_trailing_slash_stripped(self, monkeypatch: "MonkeyPatch") -> None:
        """Trailing slash on the env var value is stripped."""
        monkeypatch.setenv("UIPATH_ORCHESTRATOR_URL", "http://localhost:8080/")
        assert get_service_override("orchestrator_") == "http://localhost:8080"

    def test_case_insensitive_lookup(self, monkeypatch: "MonkeyPatch") -> None:
        """Prefix lookup is case-insensitive."""
        monkeypatch.setenv("UIPATH_AGENTHUB_URL", "http://localhost:9090")
        assert get_service_override("agenthub_") == "http://localhost:9090"
        assert get_service_override("AGENTHUB_") == "http://localhost:9090"

    def test_multiple_overrides_independent(self, monkeypatch: "MonkeyPatch") -> None:
        """Multiple services can be overridden independently."""
        monkeypatch.setenv("UIPATH_ORCHESTRATOR_URL", "http://localhost:8080")
        monkeypatch.setenv("UIPATH_DU_URL", "http://localhost:9090")
        assert get_service_override("orchestrator_") == "http://localhost:8080"
        assert get_service_override("du_") == "http://localhost:9090"
        assert get_service_override("agenthub_") is None

    def test_unrecognised_service_returns_none(
        self, monkeypatch: "MonkeyPatch"
    ) -> None:
        """A prefix not in the service map returns None."""
        monkeypatch.setenv("UIPATH_UNKNOWN_URL", "http://localhost:1111")
        assert get_service_override("unknown_") is None
