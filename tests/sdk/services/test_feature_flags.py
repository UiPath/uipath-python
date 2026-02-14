"""Unit tests for the feature flags registry."""

from typing import TYPE_CHECKING

from uipath.platform.feature_flags import configure, get, is_enabled, reset
from uipath.platform.feature_flags.feature_flags import _parse_env_value

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


class TestParseEnvValue:
    """Tests for _parse_env_value."""

    def test_true_string(self) -> None:
        assert _parse_env_value("true") is True

    def test_true_uppercase(self) -> None:
        assert _parse_env_value("TRUE") is True

    def test_true_mixed_case(self) -> None:
        assert _parse_env_value("True") is True

    def test_false_string(self) -> None:
        assert _parse_env_value("false") is False

    def test_false_uppercase(self) -> None:
        assert _parse_env_value("FALSE") is False

    def test_string_passthrough(self) -> None:
        assert _parse_env_value("gpt-4") == "gpt-4"

    def test_empty_string(self) -> None:
        assert _parse_env_value("") == ""

    def test_numeric_string(self) -> None:
        assert _parse_env_value("42") == "42"


class TestConfigure:
    """Tests for configure / reset."""

    def setup_method(self) -> None:
        reset()

    def test_configure_sets_flags(self) -> None:
        configure({"FeatureA": True, "FeatureB": "value"})
        assert get("FeatureA") is True
        assert get("FeatureB") == "value"

    def test_configure_merges(self) -> None:
        configure({"FeatureA": True})
        configure({"FeatureB": False})
        assert get("FeatureA") is True
        assert get("FeatureB") is False

    def test_configure_overwrites(self) -> None:
        configure({"FeatureA": True})
        configure({"FeatureA": False})
        assert get("FeatureA") is False

    def test_reset_clears_all(self) -> None:
        configure({"FeatureA": True})
        reset()
        assert get("FeatureA") is None


class TestGet:
    """Tests for get."""

    def setup_method(self) -> None:
        reset()

    def test_returns_default_when_unset(self) -> None:
        assert get("Missing") is None

    def test_returns_custom_default(self) -> None:
        assert get("Missing", default="fallback") == "fallback"

    def test_returns_configured_value(self) -> None:
        configure({"FeatureA": "hello"})
        assert get("FeatureA") == "hello"

    def test_env_var_overrides_configured(self, monkeypatch: "MonkeyPatch") -> None:
        configure({"FeatureA": True})
        monkeypatch.setenv("UIPATH_FEATURE_FeatureA", "false")
        assert get("FeatureA") is False

    def test_env_var_overrides_default(self, monkeypatch: "MonkeyPatch") -> None:
        monkeypatch.setenv("UIPATH_FEATURE_X", "custom")
        assert get("X", default="other") == "custom"

    def test_env_var_string_value(self, monkeypatch: "MonkeyPatch") -> None:
        monkeypatch.setenv("UIPATH_FEATURE_Model", "gpt-4-turbo")
        assert get("Model") == "gpt-4-turbo"


class TestIsEnabled:
    """Tests for is_enabled."""

    def setup_method(self) -> None:
        reset()

    def test_enabled_flag(self) -> None:
        configure({"FeatureA": True})
        assert is_enabled("FeatureA") is True

    def test_disabled_flag(self) -> None:
        configure({"FeatureA": False})
        assert is_enabled("FeatureA") is False

    def test_missing_flag_defaults_false(self) -> None:
        assert is_enabled("Missing") is False

    def test_missing_flag_custom_default(self) -> None:
        assert is_enabled("Missing", default=True) is True

    def test_truthy_string_is_enabled(self) -> None:
        configure({"FeatureA": "some-value"})
        assert is_enabled("FeatureA") is True

    def test_none_is_disabled(self) -> None:
        configure({"FeatureA": None})
        assert is_enabled("FeatureA") is False

    def test_env_override_disables(self, monkeypatch: "MonkeyPatch") -> None:
        configure({"FeatureA": True})
        monkeypatch.setenv("UIPATH_FEATURE_FeatureA", "false")
        assert is_enabled("FeatureA") is False

    def test_env_override_enables(self, monkeypatch: "MonkeyPatch") -> None:
        configure({"FeatureA": False})
        monkeypatch.setenv("UIPATH_FEATURE_FeatureA", "true")
        assert is_enabled("FeatureA") is True
