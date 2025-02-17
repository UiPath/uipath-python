import pydantic_core
import pytest

from uipath_sdk._uipath_sdk import UiPathSDK


class TestSdkConfig:
    def test_no_config(self, monkeypatch):
        monkeypatch.delenv("UIPATH_URL", raising=False)
        monkeypatch.delenv("UIPATH_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("UNATTENDED_USER_ACCESS_TOKEN", raising=False)

        with pytest.raises(pydantic_core._pydantic_core.ValidationError) as exc_info:
            UiPathSDK()

        assert exc_info.value.errors(include_url=False) == [
            {
                "type": "string_type",
                "loc": ("base_url",),
                "msg": "Input should be a valid string",
                "input": None,
            },
            {
                "type": "string_type",
                "loc": ("secret",),
                "msg": "Input should be a valid string",
                "input": None,
            },
        ]

    def test_config_from_env(self, monkeypatch):
        monkeypatch.setenv("UIPATH_URL", "https://example.com")
        monkeypatch.setenv("UIPATH_ACCESS_TOKEN", "1234567890")
        sdk = UiPathSDK()
        assert sdk._config.base_url == "https://example.com"
        assert sdk._config.secret == "1234567890"

    def test_config_from_constructor(self, monkeypatch):
        monkeypatch.delenv("UIPATH_URL", raising=False)
        monkeypatch.delenv("UIPATH_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("UNATTENDED_USER_ACCESS_TOKEN", raising=False)

        sdk = UiPathSDK(base_url="https://example.com", secret="1234567890")
        assert sdk._config.base_url == "https://example.com"
        assert sdk._config.secret == "1234567890"
