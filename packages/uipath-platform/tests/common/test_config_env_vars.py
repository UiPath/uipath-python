import pytest

from uipath.platform.common._config import UiPathConfig


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    for var in (
        "UIPATH_PROJECT_ID",
        "UIPATH_FILE_SOURCE_PROJECT_ID",
        "UIPATH_AGENT_ID",
        "UIPATH_CLOUD_USER_ID",
        "UIPATH_PROJECT_FILES_SOURCE",
    ):
        monkeypatch.delenv(var, raising=False)


class TestProjectIdFallback:
    def test_returns_file_source_when_set(self, monkeypatch):
        monkeypatch.setenv("UIPATH_FILE_SOURCE_PROJECT_ID", "file-source-id")
        monkeypatch.setenv("UIPATH_PROJECT_ID", "legacy-id")
        assert UiPathConfig.project_id == "file-source-id"

    def test_falls_back_to_legacy_when_file_source_unset(self, monkeypatch):
        monkeypatch.setenv("UIPATH_PROJECT_ID", "legacy-id")
        assert UiPathConfig.project_id == "legacy-id"

    def test_returns_none_when_neither_set(self):
        assert UiPathConfig.project_id is None


class TestAgentId:
    def test_returns_explicit_agent_id_when_set(self, monkeypatch):
        monkeypatch.setenv("UIPATH_FILE_SOURCE_PROJECT_ID", "debug-project-guid")
        monkeypatch.setenv("UIPATH_AGENT_ID", "real-agent-id")
        assert UiPathConfig.agent_id == "real-agent-id"

    def test_falls_back_to_project_id_when_agent_id_unset(self, monkeypatch):
        monkeypatch.setenv("UIPATH_PROJECT_ID", "cloud-project-id")
        assert UiPathConfig.agent_id == "cloud-project-id"

    def test_returns_none_when_neither_set(self):
        assert UiPathConfig.agent_id is None


class TestCloudUserId:
    def test_returns_value_when_set(self, monkeypatch):
        monkeypatch.setenv("UIPATH_CLOUD_USER_ID", "user-guid")
        assert UiPathConfig.cloud_user_id == "user-guid"

    def test_returns_none_when_unset(self):
        assert UiPathConfig.cloud_user_id is None


class TestProjectFilesSource:
    def test_returns_value_when_set(self, monkeypatch):
        monkeypatch.setenv("UIPATH_PROJECT_FILES_SOURCE", "Local")
        assert UiPathConfig.project_files_source == "Local"

    def test_returns_none_when_unset(self):
        assert UiPathConfig.project_files_source is None
