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
            url=f"{base_url}{org}{tenant}/orchestrator_/api/FoldersNavigation/GetFoldersForCurrentUser?searchText=test-folder-path&skip=0&take=20",
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
            == f"{base_url}{org}{tenant}/orchestrator_/api/FoldersNavigation/GetFoldersForCurrentUser?searchText=test-folder-path&skip=0&take=20"
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
            url=f"{base_url}{org}{tenant}/orchestrator_/api/FoldersNavigation/GetFoldersForCurrentUser?searchText=non-existent-folder&skip=0&take=20",
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
            == f"{base_url}{org}{tenant}/orchestrator_/api/FoldersNavigation/GetFoldersForCurrentUser?searchText=non-existent-folder&skip=0&take=20"
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
            url=f"{base_url}{org}{tenant}/orchestrator_/api/FoldersNavigation/GetFoldersForCurrentUser?searchText=test-folder-path&skip=0&take=20",
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

        folder_key = service.retrieve_key(folder_path="test-folder-path")

        assert folder_key == "test-folder-key"

        sent_request = httpx_mock.get_request()
        if sent_request is None:
            raise Exception("No request was sent")

        assert sent_request.method == "GET"
        assert (
            sent_request.url
            == f"{base_url}{org}{tenant}/orchestrator_/api/FoldersNavigation/GetFoldersForCurrentUser?searchText=test-folder-path&skip=0&take=20"
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
            url=f"{base_url}{org}{tenant}/orchestrator_/api/FoldersNavigation/GetFoldersForCurrentUser?searchText=non-existent-folder&skip=0&take=20",
            status_code=200,
            json={"PageItems": []},
        )

        folder_key = service.retrieve_key(folder_path="non-existent-folder")

        assert folder_key is None

        sent_request = httpx_mock.get_request()
        if sent_request is None:
            raise Exception("No request was sent")

        assert sent_request.method == "GET"
        assert (
            sent_request.url
            == f"{base_url}{org}{tenant}/orchestrator_/api/FoldersNavigation/GetFoldersForCurrentUser?searchText=non-existent-folder&skip=0&take=20"
        )

        assert HEADER_USER_AGENT in sent_request.headers
        assert (
            sent_request.headers[HEADER_USER_AGENT]
            == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.FolderService.retrieve_key/{version}"
        )

    def test_retrieve_key_found_on_second_page(
        self,
        httpx_mock: HTTPXMock,
        service: FolderService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        """Test that retrieve_key can find a folder on subsequent pages through pagination."""
        # First page - folder not found
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/api/FoldersNavigation/GetFoldersForCurrentUser?searchText=target-folder&skip=0&take=20",
            status_code=200,
            json={
                "PageItems": [
                    {
                        "Key": f"folder-key-{i}",
                        "FullyQualifiedName": f"other-folder-{i}",
                    }
                    for i in range(20)  # Full page of 20 items, none matching
                ]
            },
        )

        # Second page - folder found
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/api/FoldersNavigation/GetFoldersForCurrentUser?searchText=target-folder&skip=20&take=20",
            status_code=200,
            json={
                "PageItems": [
                    {
                        "Key": "target-folder-key",
                        "FullyQualifiedName": "target-folder",
                    },
                    {
                        "Key": "another-folder-key",
                        "FullyQualifiedName": "another-folder",
                    },
                ]
            },
        )

        folder_key = service.retrieve_key(folder_path="target-folder")

        assert folder_key == "target-folder-key"

        requests = httpx_mock.get_requests()
        assert len(requests) == 2

        assert requests[0].method == "GET"
        assert (
            requests[0].url
            == f"{base_url}{org}{tenant}/orchestrator_/api/FoldersNavigation/GetFoldersForCurrentUser?searchText=target-folder&skip=0&take=20"
        )

        assert requests[1].method == "GET"
        assert (
            requests[1].url
            == f"{base_url}{org}{tenant}/orchestrator_/api/FoldersNavigation/GetFoldersForCurrentUser?searchText=target-folder&skip=20&take=20"
        )

    def test_retrieve_key_not_found_after_pagination(
        self,
        httpx_mock: HTTPXMock,
        service: FolderService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        """Test that retrieve_key returns None when folder is not found after paginating through all results."""
        # First page - full page, no match
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/api/FoldersNavigation/GetFoldersForCurrentUser?searchText=missing-folder&skip=0&take=20",
            status_code=200,
            json={
                "PageItems": [
                    {
                        "Key": f"folder-key-{i}",
                        "FullyQualifiedName": f"other-folder-{i}",
                    }
                    for i in range(20)  # Full page of 20 items
                ]
            },
        )

        # Second page - no match
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/api/FoldersNavigation/GetFoldersForCurrentUser?searchText=missing-folder&skip=20&take=20",
            status_code=200,
            json={
                "PageItems": [
                    {
                        "Key": "final-folder-key",
                        "FullyQualifiedName": "final-folder",
                    },
                ]
            },
        )

        folder_key = service.retrieve_key(folder_path="missing-folder")

        assert folder_key is None

        requests = httpx_mock.get_requests()
        assert len(requests) == 2

        assert requests[0].method == "GET"
        assert (
            requests[0].url
            == f"{base_url}{org}{tenant}/orchestrator_/api/FoldersNavigation/GetFoldersForCurrentUser?searchText=missing-folder&skip=0&take=20"
        )

        assert requests[1].method == "GET"
        assert (
            requests[1].url
            == f"{base_url}{org}{tenant}/orchestrator_/api/FoldersNavigation/GetFoldersForCurrentUser?searchText=missing-folder&skip=20&take=20"
        )

    def test_retrieve_key_found_on_third_page(
        self,
        httpx_mock: HTTPXMock,
        service: FolderService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        """Test that retrieve_key can find a folder on the third page through multiple pagination requests."""
        # First page
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/api/FoldersNavigation/GetFoldersForCurrentUser?searchText=deep-folder&skip=0&take=20",
            status_code=200,
            json={
                "PageItems": [
                    {
                        "Key": f"folder-key-{i}",
                        "FullyQualifiedName": f"page1-folder-{i}",
                    }
                    for i in range(20)
                ]
            },
        )

        # Second page
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/api/FoldersNavigation/GetFoldersForCurrentUser?searchText=deep-folder&skip=20&take=20",
            status_code=200,
            json={
                "PageItems": [
                    {
                        "Key": f"folder-key-{i}",
                        "FullyQualifiedName": f"page2-folder-{i}",
                    }
                    for i in range(20)
                ]
            },
        )

        # Third page - folder found
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/api/FoldersNavigation/GetFoldersForCurrentUser?searchText=deep-folder&skip=40&take=20",
            status_code=200,
            json={
                "PageItems": [
                    {
                        "Key": "some-other-key",
                        "FullyQualifiedName": "some-other-folder",
                    },
                    {
                        "Key": "deep-folder-key",
                        "FullyQualifiedName": "deep-folder",
                    },
                ]
            },
        )

        folder_key = service.retrieve_key(folder_path="deep-folder")

        assert folder_key == "deep-folder-key"

        requests = httpx_mock.get_requests()
        assert len(requests) == 3

        expected_urls = [
            f"{base_url}{org}{tenant}/orchestrator_/api/FoldersNavigation/GetFoldersForCurrentUser?searchText=deep-folder&skip=0&take=20",
            f"{base_url}{org}{tenant}/orchestrator_/api/FoldersNavigation/GetFoldersForCurrentUser?searchText=deep-folder&skip=20&take=20",
            f"{base_url}{org}{tenant}/orchestrator_/api/FoldersNavigation/GetFoldersForCurrentUser?searchText=deep-folder&skip=40&take=20",
        ]

        for i, request in enumerate(requests):
            assert request.method == "GET"
            assert request.url == expected_urls[i]
