from unittest.mock import PropertyMock, patch

import pytest

from uipath.platform.common._config import ConfigurationManager
from uipath.platform.common._http_config import get_httpx_client_kwargs


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure licensing-related env vars are clean for every test."""
    monkeypatch.delenv("UIPATH_DISABLE_SSL_VERIFY", raising=False)


class TestGetHttpxClientKwargsHeaders:
    """Tests for header merging in get_httpx_client_kwargs()."""

    def test_no_licensing_no_caller_headers(self) -> None:
        """No headers key when neither licensing nor caller headers are provided."""
        with patch.object(
            ConfigurationManager,
            "licensing_context",
            new_callable=PropertyMock,
            return_value=None,
        ):
            result = get_httpx_client_kwargs()
        assert "headers" not in result

    def test_licensing_context_only(self) -> None:
        """Licensing header included when licensing_context is set."""
        with patch.object(
            ConfigurationManager,
            "licensing_context",
            new_callable=PropertyMock,
            return_value="test-license-ctx",
        ):
            result = get_httpx_client_kwargs()
        assert result["headers"] == {"x-uipath-licensing-context": "test-license-ctx"}

    def test_caller_headers_only(self) -> None:
        """Caller headers included when no licensing_context is set."""
        with patch.object(
            ConfigurationManager,
            "licensing_context",
            new_callable=PropertyMock,
            return_value=None,
        ):
            result = get_httpx_client_kwargs(headers={"Authorization": "Bearer tok"})
        assert result["headers"] == {"Authorization": "Bearer tok"}

    def test_licensing_and_caller_headers_merged(self) -> None:
        """Both licensing and caller headers present in result."""
        with patch.object(
            ConfigurationManager,
            "licensing_context",
            new_callable=PropertyMock,
            return_value="lic-ctx",
        ):
            result = get_httpx_client_kwargs(headers={"Authorization": "Bearer tok"})
        assert result["headers"] == {
            "x-uipath-licensing-context": "lic-ctx",
            "Authorization": "Bearer tok",
        }

    def test_caller_headers_win_on_conflict(self) -> None:
        """Caller headers override licensing headers on same key."""
        with patch.object(
            ConfigurationManager,
            "licensing_context",
            new_callable=PropertyMock,
            return_value="lic-ctx",
        ):
            result = get_httpx_client_kwargs(
                headers={"x-uipath-licensing-context": "caller-override"}
            )
        assert result["headers"] == {"x-uipath-licensing-context": "caller-override"}

    def test_result_always_contains_base_config(self) -> None:
        """SSL, timeout, and redirect config always present regardless of headers."""
        with patch.object(
            ConfigurationManager,
            "licensing_context",
            new_callable=PropertyMock,
            return_value="lic",
        ):
            result = get_httpx_client_kwargs(headers={"Authorization": "Bearer x"})
        assert result["follow_redirects"] is True
        assert result["timeout"] == 30.0
        assert "verify" in result

    def test_no_headers_key_when_empty(self) -> None:
        """Empty caller headers dict with no licensing does not add headers key."""
        with patch.object(
            ConfigurationManager,
            "licensing_context",
            new_callable=PropertyMock,
            return_value=None,
        ):
            result = get_httpx_client_kwargs(headers={})
        assert "headers" not in result
