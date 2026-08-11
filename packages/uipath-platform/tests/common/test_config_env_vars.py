from pathlib import Path

import pytest

from uipath.platform.common._config import UiPathConfig
from uipath.platform.constants import (
    ENTRY_POINTS_FILE,
    ENV_BASE_URL,
    ENV_FOLDER_KEY,
    ENV_FOLDER_PATH,
    ENV_JOB_KEY,
    ENV_ORGANIZATION_ID,
    ENV_PROCESS_KEY,
    ENV_PROJECT_KEY,
    ENV_TENANT_ID,
    ENV_TENANT_NAME,
    ENV_TRACING_ENABLED,
    ENV_UIPATH_AGENT_ID,
    ENV_UIPATH_CLOUD_USER_ID,
    ENV_UIPATH_CONFIG_PATH,
    ENV_UIPATH_PROCESS_UUID,
    ENV_UIPATH_PROCESS_VERSION,
    ENV_UIPATH_PROJECT_FILES_SOURCE,
    ENV_UIPATH_PROJECT_ID,
    ENV_UIPATH_TRACE_ID,
    EVALS_FOLDER,
    LEGACY_EVAL_FOLDER,
    STUDIO_METADATA_FILE,
    UIPATH_BINDINGS_FILE,
    UIPATH_CONFIG_FILE,
    UIPROJ_FILE,
)

# Every env var read by ConfigurationManager properties. Cleared before each
# test so "returns None when unset" assertions don't pick up the real
# environment.
_ENV_VARS = (
    ENV_UIPATH_PROJECT_ID,
    ENV_UIPATH_AGENT_ID,
    ENV_UIPATH_CLOUD_USER_ID,
    ENV_UIPATH_PROJECT_FILES_SOURCE,
    ENV_PROJECT_KEY,
    ENV_TENANT_NAME,
    ENV_TENANT_ID,
    ENV_ORGANIZATION_ID,
    ENV_BASE_URL,
    ENV_FOLDER_KEY,
    ENV_FOLDER_PATH,
    ENV_PROCESS_KEY,
    ENV_UIPATH_PROCESS_UUID,
    ENV_UIPATH_TRACE_ID,
    ENV_UIPATH_PROCESS_VERSION,
    ENV_JOB_KEY,
    ENV_UIPATH_CONFIG_PATH,
    ENV_TRACING_ENABLED,
)


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    for var in _ENV_VARS:
        monkeypatch.delenv(var, raising=False)


class TestProjectId:
    def test_reads_env_var(self, monkeypatch):
        monkeypatch.setenv(ENV_UIPATH_PROJECT_ID, "file-source-id")
        assert UiPathConfig.project_id == "file-source-id"

    def test_returns_none_when_unset(self):
        assert UiPathConfig.project_id is None


class TestAgentId:
    def test_returns_explicit_agent_id_when_set(self, monkeypatch):
        monkeypatch.setenv(ENV_UIPATH_PROJECT_ID, "debug-project-guid")
        monkeypatch.setenv(ENV_UIPATH_AGENT_ID, "real-agent-id")
        assert UiPathConfig.agent_id == "real-agent-id"

    def test_falls_back_to_project_id_when_agent_id_unset(self, monkeypatch):
        monkeypatch.setenv(ENV_UIPATH_PROJECT_ID, "cloud-project-id")
        assert UiPathConfig.agent_id == "cloud-project-id"

    def test_returns_none_when_neither_set(self):
        assert UiPathConfig.agent_id is None


class TestCloudUserId:
    def test_returns_value_when_set(self, monkeypatch):
        monkeypatch.setenv(ENV_UIPATH_CLOUD_USER_ID, "user-guid")
        assert UiPathConfig.cloud_user_id == "user-guid"

    def test_returns_none_when_unset(self):
        assert UiPathConfig.cloud_user_id is None


class TestProjectFilesSource:
    def test_returns_value_when_set(self, monkeypatch):
        monkeypatch.setenv(ENV_UIPATH_PROJECT_FILES_SOURCE, "Local")
        assert UiPathConfig.project_files_source == "Local"

    def test_returns_none_when_unset(self):
        assert UiPathConfig.project_files_source is None


@pytest.mark.parametrize(
    ("prop", "env_var", "value"),
    [
        ("project_key", ENV_PROJECT_KEY, "proj-key"),
        ("tenant_name", ENV_TENANT_NAME, "my-tenant"),
        ("tenant_id", ENV_TENANT_ID, "tenant-guid"),
        ("organization_id", ENV_ORGANIZATION_ID, "org-guid"),
        ("base_url", ENV_BASE_URL, "https://cloud.uipath.com/org/tenant"),
        ("folder_key", ENV_FOLDER_KEY, "folder-guid"),
        ("folder_path", ENV_FOLDER_PATH, "Shared/My Folder"),
        ("process_key", ENV_PROCESS_KEY, "process-key"),
        ("process_uuid", ENV_UIPATH_PROCESS_UUID, "process-uuid"),
        ("trace_id", ENV_UIPATH_TRACE_ID, "trace-id"),
        ("process_version", ENV_UIPATH_PROCESS_VERSION, "1.2.3"),
        ("job_key", ENV_JOB_KEY, "job-guid"),
    ],
)
class TestOptionalEnvVarProperties:
    def test_returns_value_when_set(self, monkeypatch, prop, env_var, value):
        monkeypatch.setenv(env_var, value)
        assert getattr(UiPathConfig, prop) == value

    def test_returns_none_when_unset(self, monkeypatch, prop, env_var, value):
        assert getattr(UiPathConfig, prop) is None


class TestFileNameProperties:
    def test_config_file_name(self):
        assert UiPathConfig.config_file_name == UIPATH_CONFIG_FILE

    def test_bindings_file_path(self):
        assert UiPathConfig.bindings_file_path == Path(UIPATH_BINDINGS_FILE)

    def test_entry_points_file_path(self):
        assert UiPathConfig.entry_points_file_path == Path(ENTRY_POINTS_FILE)

    def test_uiproj_file_path(self):
        assert UiPathConfig.uiproj_file_path == Path(UIPROJ_FILE)

    def test_studio_metadata_file_path(self):
        assert UiPathConfig.studio_metadata_file_path == Path(
            ".uipath", STUDIO_METADATA_FILE
        )

    def test_config_file_path_defaults_to_config_file(self):
        assert UiPathConfig.config_file_path == Path(UIPATH_CONFIG_FILE)

    def test_config_file_path_honors_override(self, monkeypatch):
        monkeypatch.setenv(ENV_UIPATH_CONFIG_PATH, "custom/config.json")
        assert UiPathConfig.config_file_path == Path("custom/config.json")


class TestIsStudioProject:
    def test_true_when_project_id_set(self, monkeypatch):
        monkeypatch.setenv(ENV_UIPATH_PROJECT_ID, "some-id")
        assert UiPathConfig.is_studio_project is True

    def test_false_when_project_id_unset(self):
        assert UiPathConfig.is_studio_project is False


class TestIsTracingEnabled:
    def test_defaults_to_true_when_unset(self):
        assert UiPathConfig.is_tracing_enabled is True

    @pytest.mark.parametrize("value", ["false", "False", "FALSE"])
    def test_false_when_disabled(self, monkeypatch, value):
        monkeypatch.setenv(ENV_TRACING_ENABLED, value)
        assert UiPathConfig.is_tracing_enabled is False

    def test_true_when_explicitly_enabled(self, monkeypatch):
        monkeypatch.setenv(ENV_TRACING_ENABLED, "true")
        assert UiPathConfig.is_tracing_enabled is True


class TestEvalFolderDetection:
    def test_has_legacy_eval_folder(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        assert UiPathConfig.has_legacy_eval_folder is False
        (tmp_path / LEGACY_EVAL_FOLDER).mkdir()
        assert UiPathConfig.has_legacy_eval_folder is True

    def test_has_eval_folder(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        assert UiPathConfig.has_eval_folder is False
        (tmp_path / EVALS_FOLDER).mkdir()
        assert UiPathConfig.has_eval_folder is True
