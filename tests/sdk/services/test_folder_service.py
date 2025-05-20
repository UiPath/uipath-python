import pytest
from pytest_httpx import HTTPXMock

from uipath._config import Config
from uipath._execution_context import ExecutionContext
from uipath._services.folder_service import FolderService
from uipath._utils.constants import HEADER_USER_AGENT


@pytest.fixture
def service(
    config: Config,
    execution_context: ExecutionContext,
    monkeypatch: pytest.MonkeyPatch,
) -> FolderService:
    monkeypatch.setenv("UIPATH_FOLDER_PATH", "test-folder-path")
    return FolderService(config=config, execution_context=execution_context)


class TestFolderService:
    def test_retrieve_key_by_folder_path(
        self,
        httpx_mock: HTTPXMock,
        service: FolderService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/api/FoldersNavigation/GetFoldersForCurrentUser?searchText=test-folder-path&take=1",
            status_code=200,
            json={
                "PageItems": [
                    {
                        "Key": "test-folder-key",
                        "FullyQualifiedName": "test-folder-path",
                    }
                ]
            },
        )

        with pytest.warns(DeprecationWarning, match="Use retrieve_key instead"):
            folder_key = service.retrieve_key_by_folder_path("test-folder-path")

        assert folder_key == "test-folder-key"

        sent_request = httpx_mock.get_request()
        if sent_request is None:
            raise Exception("No request was sent")

        assert sent_request.method == "GET"
        assert (
            sent_request.url
            == f"{base_url}{org}{tenant}/orchestrator_/api/FoldersNavigation/GetFoldersForCurrentUser?searchText=test-folder-path&take=1"
        )

        assert HEADER_USER_AGENT in sent_request.headers
        assert (
            sent_request.headers[HEADER_USER_AGENT]
            == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.FolderService.retrieve_key/{version}"
        )

    def test_retrieve_key_by_folder_path_not_found(
        self,
        httpx_mock: HTTPXMock,
        service: FolderService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/api/FoldersNavigation/GetFoldersForCurrentUser?searchText=non-existent-folder&take=1",
            status_code=200,
            json={"PageItems": []},
        )

        with pytest.warns(DeprecationWarning, match="Use retrieve_key instead"):
            folder_key = service.retrieve_key_by_folder_path("non-existent-folder")

        assert folder_key is None

        sent_request = httpx_mock.get_request()
        if sent_request is None:
            raise Exception("No request was sent")

        assert sent_request.method == "GET"
        assert (
            sent_request.url
            == f"{base_url}{org}{tenant}/orchestrator_/api/FoldersNavigation/GetFoldersForCurrentUser?searchText=non-existent-folder&take=1"
        )

        assert HEADER_USER_AGENT in sent_request.headers
        assert (
            sent_request.headers[HEADER_USER_AGENT]
            == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.FolderService.retrieve_key/{version}"
        )

    def test_retrieve_key(
        self,
        httpx_mock: HTTPXMock,
        service: FolderService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/api/FoldersNavigation/GetFoldersForCurrentUser?searchText=test-folder-path&take=1",
            status_code=200,
            json={
                "PageItems": [
                    {
                        "Key": "test-folder-key",
                        "FullyQualifiedName": "test-folder-path",
                    }
                ]
            },
        )

        folder_key = service.retrieve_key_by_folder_path("test-folder-path")

        assert folder_key == "test-folder-key"

        sent_request = httpx_mock.get_request()
        if sent_request is None:
            raise Exception("No request was sent")

        assert sent_request.method == "GET"
        assert (
            sent_request.url
            == f"{base_url}{org}{tenant}/orchestrator_/api/FoldersNavigation/GetFoldersForCurrentUser?searchText=test-folder-path&take=1"
        )

        assert HEADER_USER_AGENT in sent_request.headers
        assert (
            sent_request.headers[HEADER_USER_AGENT]
            == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.FolderService.retrieve_key/{version}"
        )

    def test_retrieve_key_not_found(
        self,
        httpx_mock: HTTPXMock,
        service: FolderService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/api/FoldersNavigation/GetFoldersForCurrentUser?searchText=non-existent-folder&take=1",
            status_code=200,
            json={"PageItems": []},
        )

        folder_key = service.retrieve_key_by_folder_path("non-existent-folder")

        assert folder_key is None

        sent_request = httpx_mock.get_request()
        if sent_request is None:
            raise Exception("No request was sent")

        assert sent_request.method == "GET"
        assert (
            sent_request.url
            == f"{base_url}{org}{tenant}/orchestrator_/api/FoldersNavigation/GetFoldersForCurrentUser?searchText=non-existent-folder&take=1"
        )

        assert HEADER_USER_AGENT in sent_request.headers
        assert (
            sent_request.headers[HEADER_USER_AGENT]
            == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.FolderService.retrieve_key/{version}"
        )
