import json

import pytest

from uipath.platform.common._config import ConfigurationManager


@pytest.fixture
def config_manager(tmp_path, monkeypatch):
    """Create a fresh ConfigurationManager pointing to a temp config file."""
    mgr = ConfigurationManager.__new__(ConfigurationManager)
    config_file = tmp_path / "uipath.json"
    monkeypatch.setenv("UIPATH_CONFIG_PATH", str(config_file))
    mgr.reset()
    return mgr, config_file


class TestConfigurationManagerIsConversational:
    def test_is_conversational_true(self, config_manager):
        mgr, config_file = config_manager
        config_file.write_text(
            json.dumps({"runtimeOptions": {"isConversational": True}})
        )
        assert mgr.is_conversational is True

    def test_is_conversational_false(self, config_manager):
        mgr, config_file = config_manager
        config_file.write_text(
            json.dumps({"runtimeOptions": {"isConversational": False}})
        )
        assert mgr.is_conversational is False

    def test_is_conversational_missing_runtime_options(self, config_manager):
        mgr, config_file = config_manager
        config_file.write_text(json.dumps({"runtime": {}}))
        assert mgr.is_conversational is False

    def test_is_conversational_missing_config_file(self, config_manager):
        mgr, _ = config_manager
        # config_file not created, so it doesn't exist
        assert mgr.is_conversational is False
