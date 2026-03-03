"""Unit tests for the feature flags registry."""

from typing import TYPE_CHECKING

from uipath.core.feature_flags import FeatureFlags
from uipath.core.feature_flags.feature_flags import _parse_env_value

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

    def test_json_dict(self) -> None:
        result = _parse_env_value('{"model": "gpt-4", "enabled": true}')
        assert result == {"model": "gpt-4", "enabled": True}

    def test_json_list(self) -> None:
        result = _parse_env_value('["a", "b", "c"]')
        assert result == ["a", "b", "c"]

    def test_json_nested_dict(self) -> None:
        result = _parse_env_value('{"outer": {"inner": 1}}')
        assert result == {"outer": {"inner": 1}}

    def test_float_string_stays_string(self) -> None:
        assert _parse_env_value("3.14") == "3.14"

    def test_plain_string_not_json(self) -> None:
        assert _parse_env_value("gpt-4") == "gpt-4"


class TestConfigureFlags:
    """Tests for configure_flags / reset_flags."""

    def setup_method(self) -> None:
        FeatureFlags.reset_flags()

    def test_configure_sets_flags(self) -> None:
        FeatureFlags.configure_flags({"FeatureA": True, "FeatureB": "value"})
        assert FeatureFlags.get_flag("FeatureA") is True
        assert FeatureFlags.get_flag("FeatureB") == "value"

    def test_configure_merges(self) -> None:
        FeatureFlags.configure_flags({"FeatureA": True})
        FeatureFlags.configure_flags({"FeatureB": False})
        assert FeatureFlags.get_flag("FeatureA") is True
        assert FeatureFlags.get_flag("FeatureB") is False

    def test_configure_overwrites(self) -> None:
        FeatureFlags.configure_flags({"FeatureA": True})
        FeatureFlags.configure_flags({"FeatureA": False})
        assert FeatureFlags.get_flag("FeatureA") is False

    def test_reset_clears_all(self) -> None:
        FeatureFlags.configure_flags({"FeatureA": True})
        FeatureFlags.reset_flags()
        assert FeatureFlags.get_flag("FeatureA") is None


class TestGetFlag:
    """Tests for get_flag."""

    def setup_method(self) -> None:
        FeatureFlags.reset_flags()

    def test_returns_default_when_unset(self) -> None:
        assert FeatureFlags.get_flag("Missing") is None

    def test_returns_custom_default(self) -> None:
        assert FeatureFlags.get_flag("Missing", default="fallback") == "fallback"

    def test_returns_configured_value(self) -> None:
        FeatureFlags.configure_flags({"FeatureA": "hello"})
        assert FeatureFlags.get_flag("FeatureA") == "hello"

    def test_configured_value_takes_precedence_over_env_var(
        self, monkeypatch: "MonkeyPatch"
    ) -> None:
        FeatureFlags.configure_flags({"FeatureA": True})
        monkeypatch.setenv("UIPATH_FEATURE_FeatureA", "false")
        assert FeatureFlags.get_flag("FeatureA") is True

    def test_env_var_used_when_nothing_configured(
        self, monkeypatch: "MonkeyPatch"
    ) -> None:
        monkeypatch.setenv("UIPATH_FEATURE_X", "custom")
        assert FeatureFlags.get_flag("X", default="other") == "custom"

    def test_env_var_string_value(self, monkeypatch: "MonkeyPatch") -> None:
        monkeypatch.setenv("UIPATH_FEATURE_Model", "gpt-4-turbo")
        assert FeatureFlags.get_flag("Model") == "gpt-4-turbo"

    def test_env_var_json_dict(self, monkeypatch: "MonkeyPatch") -> None:
        monkeypatch.setenv("UIPATH_FEATURE_Models", '{"gpt-4": true, "claude": false}')
        assert FeatureFlags.get_flag("Models") == {"gpt-4": True, "claude": False}

    def test_env_var_json_list(self, monkeypatch: "MonkeyPatch") -> None:
        monkeypatch.setenv("UIPATH_FEATURE_AllowedModels", '["gpt-4", "claude"]')
        assert FeatureFlags.get_flag("AllowedModels") == ["gpt-4", "claude"]


class TestIsFlagEnabled:
    """Tests for is_flag_enabled."""

    def setup_method(self) -> None:
        FeatureFlags.reset_flags()

    def test_enabled_flag(self) -> None:
        FeatureFlags.configure_flags({"FeatureA": True})
        assert FeatureFlags.is_flag_enabled("FeatureA") is True

    def test_disabled_flag(self) -> None:
        FeatureFlags.configure_flags({"FeatureA": False})
        assert FeatureFlags.is_flag_enabled("FeatureA") is False

    def test_missing_flag_defaults_false(self) -> None:
        assert FeatureFlags.is_flag_enabled("Missing") is False

    def test_missing_flag_custom_default(self) -> None:
        assert FeatureFlags.is_flag_enabled("Missing", default=True) is True

    def test_truthy_string_is_enabled(self) -> None:
        FeatureFlags.configure_flags({"FeatureA": "some-value"})
        assert FeatureFlags.is_flag_enabled("FeatureA") is True

    def test_none_is_disabled(self) -> None:
        FeatureFlags.configure_flags({"FeatureA": None})
        assert FeatureFlags.is_flag_enabled("FeatureA") is False

    def test_configured_value_takes_precedence_over_env_var(
        self, monkeypatch: "MonkeyPatch"
    ) -> None:
        FeatureFlags.configure_flags({"FeatureA": True})
        monkeypatch.setenv("UIPATH_FEATURE_FeatureA", "false")
        assert FeatureFlags.is_flag_enabled("FeatureA") is True

    def test_env_var_used_when_nothing_configured(
        self, monkeypatch: "MonkeyPatch"
    ) -> None:
        monkeypatch.setenv("UIPATH_FEATURE_FeatureA", "true")
        assert FeatureFlags.is_flag_enabled("FeatureA") is True
