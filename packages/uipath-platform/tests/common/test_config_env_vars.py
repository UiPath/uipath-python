"""Tests for the env-var-aware properties on ConfigurationManager.

Covers the file-source / agent / cloud-user split introduced for local-workspace
eval runs. Cloud-project runs continue to use the legacy single-id behaviour
(no new env vars set), and the tests assert that fallback explicitly.
"""

import pytest

from uipath.platform.common._config import UiPathConfig


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    """Clear all env vars touched by these tests so each starts from a clean slate.

    ConfigurationManager is a singleton and its properties read os.environ on
    every access, so setting/unsetting via monkeypatch is sufficient — no
    instance reset needed.
    """
    for var in (
        "UIPATH_PROJECT_ID",
        "UIPATH_FILE_SOURCE_PROJECT_ID",
        "UIPATH_AGENT_ID",
        "UIPATH_CLOUD_USER_ID",
        "UIPATH_PROJECT_FILES_SOURCE",
    ):
        monkeypatch.delenv(var, raising=False)


class TestProjectIdFallback:
    """project_id prefers UIPATH_FILE_SOURCE_PROJECT_ID, falls back to UIPATH_PROJECT_ID."""

    def test_returns_file_source_when_set(self, monkeypatch):
        monkeypatch.setenv("UIPATH_FILE_SOURCE_PROJECT_ID", "file-source-id")
        monkeypatch.setenv("UIPATH_PROJECT_ID", "legacy-id")
        assert UiPathConfig.project_id == "file-source-id"

    def test_falls_back_to_legacy_when_file_source_unset(self, monkeypatch):
        # Cloud projects today only set UIPATH_PROJECT_ID; that path must keep
        # working so existing deployments aren't broken.
        monkeypatch.setenv("UIPATH_PROJECT_ID", "legacy-id")
        assert UiPathConfig.project_id == "legacy-id"

    def test_returns_none_when_neither_set(self):
        assert UiPathConfig.project_id is None


class TestAgentId:
    """agent_id is the logical agent. Distinct from project_id for local workspaces."""

    def test_returns_explicit_agent_id_when_set(self, monkeypatch):
        # Local-workspace eval scenario: file source is the cloud debug project,
        # but AgentId is the user's local agent UUID. Telemetry should tag the
        # logical agent so dashboards group by what the user authored.
        monkeypatch.setenv("UIPATH_FILE_SOURCE_PROJECT_ID", "debug-project-guid")
        monkeypatch.setenv("UIPATH_AGENT_ID", "real-agent-id")
        assert UiPathConfig.agent_id == "real-agent-id"

    def test_falls_back_to_project_id_when_agent_id_unset(self, monkeypatch):
        # Cloud-project scenario: only UIPATH_PROJECT_ID is set; agent_id must
        # equal it so existing telemetry semantics are preserved.
        monkeypatch.setenv("UIPATH_PROJECT_ID", "cloud-project-id")
        assert UiPathConfig.agent_id == "cloud-project-id"

    def test_returns_none_when_neither_set(self):
        assert UiPathConfig.agent_id is None


class TestCloudUserId:
    """cloud_user_id reads UIPATH_CLOUD_USER_ID. Returns None when unset (callers
    fall back to JWT extraction)."""

    def test_returns_value_when_set(self, monkeypatch):
        monkeypatch.setenv("UIPATH_CLOUD_USER_ID", "user-guid")
        assert UiPathConfig.cloud_user_id == "user-guid"

    def test_returns_none_when_unset(self):
        # JWT fallback is a separate concern handled by call sites; the property
        # itself returns None and lets the caller decide.
        assert UiPathConfig.cloud_user_id is None


class TestProjectFilesSource:
    """project_files_source surfaces 'Local' or 'Cloud' for telemetry tagging."""

    def test_returns_value_when_set(self, monkeypatch):
        monkeypatch.setenv("UIPATH_PROJECT_FILES_SOURCE", "Local")
        assert UiPathConfig.project_files_source == "Local"

    def test_returns_none_when_unset(self):
        assert UiPathConfig.project_files_source is None
