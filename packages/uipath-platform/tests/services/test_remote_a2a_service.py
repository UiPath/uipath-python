from unittest.mock import AsyncMock, Mock, patch

import pytest

from uipath.platform import UiPathApiConfig, UiPathExecutionContext
from uipath.platform.agenthub._remote_a2a_service import RemoteA2aService
from uipath.platform.common._bindings import (
    GenericResourceOverwrite,
    _resource_overwrites,
)
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
        spec = service._retrieve_spec(name="weather", folder_path=None)

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

        spec = service._retrieve_spec(name="weather", folder_path="MyFolder")

        assert spec.headers[HEADER_FOLDER_KEY] == "resolved-folder-key"

    def test_encodes_display_name_in_lookup_path(
        self, service: RemoteA2aService
    ) -> None:
        spec = service._retrieve_spec(name="Friendly Agent/Europe", folder_path=None)

        assert "remote-a2a-agents/Friendly%20Agent%2FEurope" in str(spec.endpoint)


class TestRetrieveByName:
    def test_retrieves_by_display_name(self, service: RemoteA2aService) -> None:
        response = Mock()
        response.json.return_value = {
            "name": "Friendly Agent/Europe",
            "slug": "friendly-agent-europe",
        }

        with patch.object(service, "request", return_value=response) as request:
            agent = service.retrieve("Friendly Agent/Europe")

        assert agent.name == "Friendly Agent/Europe"
        assert "remote-a2a-agents/Friendly%20Agent%2FEurope" in str(
            request.call_args.kwargs["url"]
        )

    def test_applies_display_name_binding(self, service: RemoteA2aService) -> None:
        response = Mock()
        response.json.return_value = {
            "name": "Replacement Agent",
            "slug": "replacement-agent",
        }
        overwrite = GenericResourceOverwrite(
            resource_type="remoteA2aAgent",
            name="Replacement Agent",
            folder_path="Replacement Folder",
        )
        token = _resource_overwrites.set({"remoteA2aAgent.Original Agent": overwrite})

        try:
            with (
                patch.object(service, "request", return_value=response) as request,
                patch.object(
                    service._folders_service,
                    "retrieve_folder_key",
                    return_value="replacement-folder-key",
                ),
            ):
                service.retrieve("Original Agent")
        finally:
            _resource_overwrites.reset(token)

        assert "remote-a2a-agents/Replacement%20Agent" in str(
            request.call_args.kwargs["url"]
        )
        assert (
            request.call_args.kwargs["headers"][HEADER_FOLDER_KEY]
            == "replacement-folder-key"
        )

    @pytest.mark.anyio
    async def test_retrieves_by_display_name_async(
        self, service: RemoteA2aService
    ) -> None:
        response = Mock()
        response.json.return_value = {
            "name": "Friendly Agent/Europe",
            "slug": "friendly-agent-europe",
        }

        with patch.object(
            service,
            "request_async",
            new=AsyncMock(return_value=response),
        ) as request:
            agent = await service.retrieve_async("Friendly Agent/Europe")

        assert agent.name == "Friendly Agent/Europe"
        assert "remote-a2a-agents/Friendly%20Agent%2FEurope" in str(
            request.call_args.kwargs["url"]
        )
