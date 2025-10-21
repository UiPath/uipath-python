import pytest

from uipath import UiPath
from uipath.models.errors import BaseUrlMissingError


class TestSdkConfig:
    def test_no_config(self, monkeypatch):
        monkeypatch.delenv("UIPATH_URL", raising=False)
        monkeypatch.delenv("UIPATH_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("UNATTENDED_USER_ACCESS_TOKEN", raising=False)

        with pytest.raises(BaseUrlMissingError) as exc_info:
            UiPath()

        assert (
            str(exc_info.value)
            == "Authentication required. Please run \033[1muipath auth\033[22m or set the base URL via the UIPATH_URL environment variable."
        )

    def test_config_from_env(self, monkeypatch):
        monkeypatch.setenv("UIPATH_URL", "https://example.com")
        monkeypatch.setenv("UIPATH_ACCESS_TOKEN", "1234567890")
        sdk = UiPath()
        assert sdk._config.base_url == "https://example.com"
        assert sdk._config.secret == "1234567890"

    def test_config_from_constructor(self, monkeypatch):
        monkeypatch.delenv("UIPATH_URL", raising=False)
        monkeypatch.delenv("UIPATH_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("UNATTENDED_USER_ACCESS_TOKEN", raising=False)

        sdk = UiPath(base_url="https://example.com", secret="1234567890")
        assert sdk._config.base_url == "https://example.com"
        assert sdk._config.secret == "1234567890"
