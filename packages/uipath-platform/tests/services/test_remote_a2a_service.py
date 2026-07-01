import pytest

from uipath.platform import UiPathApiConfig, UiPathExecutionContext
from uipath.platform.agenthub._remote_a2a_service import RemoteA2aService
from uipath.platform.constants import HEADER_FOLDER_KEY
from uipath.platform.orchestrator._folder_service import FolderService


@pytest.fixture
def folders_service(
    config: UiPathApiConfig,
    execution_context: UiPathExecutionContext,
    monkeypatch: pytest.MonkeyPatch,
) -> FolderService:
    monkeypatch.setenv("UIPATH_FOLDER_KEY", "context-folder-key")
    return FolderService(config=config, execution_context=execution_context)


@pytest.fixture
def service(
    config: UiPathApiConfig,
    execution_context: UiPathExecutionContext,
    folders_service: FolderService,
    monkeypatch: pytest.MonkeyPatch,
) -> RemoteA2aService:
    monkeypatch.setenv("UIPATH_FOLDER_KEY", "context-folder-key")
    return RemoteA2aService(
        config=config,
        execution_context=execution_context,
        folders_service=folders_service,
    )


class TestRetrieveSpecFolderResolution:
    def test_falls_back_to_folder_context_when_folder_path_missing(
        self, service: RemoteA2aService
    ) -> None:
        """No folder_path (e.g. local debug) must not raise; it falls back to context."""
        spec = service._retrieve_spec(slug="weather", folder_path=None)

        assert "remote-a2a-agents/weather" in str(spec.endpoint)
        assert spec.headers[HEADER_FOLDER_KEY] == "context-folder-key"

    def test_resolves_explicit_folder_path(
        self, service: RemoteA2aService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            service._folders_service,
            "retrieve_folder_key",
            lambda folder_path: "resolved-folder-key",
        )

        spec = service._retrieve_spec(slug="weather", folder_path="MyFolder")

        assert spec.headers[HEADER_FOLDER_KEY] == "resolved-folder-key"
