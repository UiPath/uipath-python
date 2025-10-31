"""Tests for FolderService key retrieval and performance - Phase 4b."""

import pytest
from pytest_httpx import HTTPXMock

from uipath._config import Config
from uipath._execution_context import ExecutionContext
from uipath._services.folder_service import FolderService


@pytest.fixture
def folder_service(
    config: Config, execution_context: ExecutionContext
) -> FolderService:
    """FolderService fixture for testing."""
    return FolderService(config=config, execution_context=execution_context)


class TestFolderServiceKeyRetrieval:
    """Test FolderService retrieve methods and O(n) performance characteristics."""

    def test_retrieve_by_key_makes_multiple_requests_for_pagination(
        self,
        httpx_mock: HTTPXMock,
        folder_service: FolderService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test retrieve() by key iterates through list() (O(n) behavior)."""
        # Mock first page of folders (full page of 100, no match)
        httpx_mock.add_response(
            json={
                "value": [
                    {
                        "Key": f"folder-key-{i}",
                        "DisplayName": f"Folder{i}",
                        "FullyQualifiedName": f"Shared/Folder{i}",
                        "Id": i,
                    }
                    for i in range(1, 101)  # 100 items to trigger next page
                ]
            }
        )

        # Mock second page with target folder
        httpx_mock.add_response(
            json={
                "value": [
                    {
                        "Key": "folder-key-target",
                        "DisplayName": "TargetFolder",
                        "FullyQualifiedName": "Shared/TargetFolder",
                        "Id": 101,
                    }
                ]
            }
        )

        folder = folder_service.retrieve(key="folder-key-target")

        assert folder.key == "folder-key-target"
        assert folder.display_name == "TargetFolder"

        # Verify multiple requests were made (pagination through list)
        requests = httpx_mock.get_requests()
        assert len(requests) == 2  # Two pages fetched

    def test_retrieve_by_key_raises_lookup_error_if_not_found(
        self,
        httpx_mock: HTTPXMock,
        folder_service: FolderService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test retrieve() by key raises LookupError when folder not found."""
        # Mock empty response
        httpx_mock.add_response(json={"value": []})

        with pytest.raises(
            LookupError, match="Folder with key 'non-existent' not found"
        ):
            folder_service.retrieve(key="non-existent")

    def test_retrieve_by_display_name_uses_odata_filter(
        self,
        httpx_mock: HTTPXMock,
        folder_service: FolderService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test retrieve() by display_name uses efficient OData filter (not O(n))."""
        httpx_mock.add_response(
            json={
                "value": [
                    {
                        "Key": "folder-key-123",
                        "DisplayName": "Finance",
                        "FullyQualifiedName": "Shared/Finance",
                        "Id": 1,
                    }
                ]
            }
        )

        folder = folder_service.retrieve(display_name="Finance")

        assert folder.key == "folder-key-123"
        assert folder.display_name == "Finance"

        request = httpx_mock.get_request()
        assert request is not None
        assert "%24filter" in str(request.url) or "$filter" in str(request.url)
        assert "DisplayName+eq" in str(request.url)

    def test_retrieve_by_display_name_escapes_quotes(
        self,
        httpx_mock: HTTPXMock,
        folder_service: FolderService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test retrieve() by display_name escapes single quotes for OData."""
        httpx_mock.add_response(
            json={
                "value": [
                    {
                        "Key": "folder-key-123",
                        "DisplayName": "Client's Folder",
                        "FullyQualifiedName": "Shared/Client's Folder",
                        "Id": 1,
                    }
                ]
            }
        )

        folder = folder_service.retrieve(display_name="Client's Folder")

        assert folder.display_name == "Client's Folder"

        request = httpx_mock.get_request()
        assert request is not None
        # Verify quote escaping: ' becomes '' in OData filter
        url_str = str(request.url)
        assert "Client''s" in url_str or "Client%27%27s" in url_str

    def test_retrieve_by_display_name_raises_lookup_error_if_not_found(
        self,
        httpx_mock: HTTPXMock,
        folder_service: FolderService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test retrieve() by display_name raises LookupError when not found."""
        httpx_mock.add_response(json={"value": []})

        with pytest.raises(
            LookupError, match="Folder with display_name 'NonExistent' not found"
        ):
            folder_service.retrieve(display_name="NonExistent")

    def test_retrieve_requires_key_or_display_name(
        self,
        folder_service: FolderService,
    ) -> None:
        """Test retrieve() raises ValueError if neither key nor display_name provided."""
        with pytest.raises(
            ValueError, match="Either 'key' or 'display_name' must be provided"
        ):
            folder_service.retrieve()

    def test_retrieve_by_path_uses_odata_filter(
        self,
        httpx_mock: HTTPXMock,
        folder_service: FolderService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test retrieve_by_path() uses efficient OData filter."""
        httpx_mock.add_response(
            json={
                "value": [
                    {
                        "Key": "folder-key-123",
                        "DisplayName": "Finance",
                        "FullyQualifiedName": "Shared/Finance",
                        "Id": 1,
                    }
                ]
            }
        )

        folder = folder_service.retrieve_by_path("Shared/Finance")

        assert folder.fully_qualified_name == "Shared/Finance"

        request = httpx_mock.get_request()
        assert request is not None
        assert "%24filter" in str(request.url) or "$filter" in str(request.url)
        assert "FullyQualifiedName+eq" in str(request.url)

    def test_retrieve_by_path_escapes_quotes(
        self,
        httpx_mock: HTTPXMock,
        folder_service: FolderService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test retrieve_by_path() escapes single quotes in path."""
        httpx_mock.add_response(
            json={
                "value": [
                    {
                        "Key": "folder-key-123",
                        "DisplayName": "Client's Folder",
                        "FullyQualifiedName": "Shared/Client's Folder",
                        "Id": 1,
                    }
                ]
            }
        )

        folder = folder_service.retrieve_by_path("Shared/Client's Folder")

        assert folder.fully_qualified_name == "Shared/Client's Folder"

        # Verify quote escaping: ' becomes '' in OData filter
        request = httpx_mock.get_request()
        assert request is not None
        url_str = str(request.url)
        assert "Client''s" in url_str or "Client%27%27s" in url_str

    def test_retrieve_by_path_raises_lookup_error_if_not_found(
        self,
        httpx_mock: HTTPXMock,
        folder_service: FolderService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test retrieve_by_path() raises LookupError when path not found."""
        httpx_mock.add_response(json={"value": []})

        with pytest.raises(
            LookupError, match="Folder with path 'Shared/NonExistent' not found"
        ):
            folder_service.retrieve_by_path("Shared/NonExistent")

    def test_retrieve_key_paginates_through_folders(
        self,
        httpx_mock: HTTPXMock,
        folder_service: FolderService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test retrieve_key() paginates through folders to find key."""
        # Mock first page (full page of 20, no match) - take=20 in retrieve_key
        httpx_mock.add_response(
            json={
                "PageItems": [
                    {"Key": f"folder-{i}", "FullyQualifiedName": f"Shared/Folder{i}"}
                    for i in range(1, 21)  # 20 items to trigger next page
                ]
            }
        )

        # Mock second page with target
        httpx_mock.add_response(
            json={
                "PageItems": [
                    {"Key": "folder-target", "FullyQualifiedName": "Shared/Finance"},
                ]
            }
        )

        key = folder_service.retrieve_key(folder_path="Shared/Finance")

        assert key == "folder-target"

        requests = httpx_mock.get_requests()
        assert len(requests) == 2

    def test_retrieve_key_returns_none_if_not_found(
        self,
        httpx_mock: HTTPXMock,
        folder_service: FolderService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test retrieve_key() returns None when folder path not found."""
        # Mock page with no match and less than take count (end of results)
        httpx_mock.add_response(
            json={
                "PageItems": [
                    {"Key": "folder-1", "FullyQualifiedName": "Shared/Folder1"},
                ]
            }
        )

        key = folder_service.retrieve_key(folder_path="Shared/NonExistent")

        assert key is None

    def test_retrieve_key_searches_using_folder_name(
        self,
        httpx_mock: HTTPXMock,
        folder_service: FolderService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test retrieve_key() uses folder name (last segment) in search."""
        httpx_mock.add_response(
            json={
                "PageItems": [
                    {"Key": "folder-key-123", "FullyQualifiedName": "Shared/Finance"},
                ]
            }
        )

        folder_service.retrieve_key(folder_path="Shared/Finance")

        # Verify search text uses only "Finance" (last segment)
        request = httpx_mock.get_request()
        assert request is not None
        assert "searchText=Finance" in str(request.url)

    def test_list_paginates_automatically(
        self,
        httpx_mock: HTTPXMock,
        folder_service: FolderService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test list() automatically paginates through all folders."""
        # Mock first page (full page, triggers next request)
        httpx_mock.add_response(
            json={
                "value": [
                    {
                        "Key": f"folder-{i}",
                        "DisplayName": f"Folder{i}",
                        "FullyQualifiedName": f"Shared/Folder{i}",
                        "Id": i,
                    }
                    for i in range(1, 101)  # 100 items (default page size)
                ]
            }
        )

        # Mock second page (partial, end of results)
        httpx_mock.add_response(
            json={
                "value": [
                    {
                        "Key": "folder-101",
                        "DisplayName": "Folder101",
                        "FullyQualifiedName": "Shared/Folder101",
                        "Id": 101,
                    }
                ]
            }
        )

        folders = list(folder_service.list())

        assert len(folders) == 101  # 100 + 1
        assert folders[0].key == "folder-1"
        assert folders[100].key == "folder-101"

    def test_list_with_filter(
        self,
        httpx_mock: HTTPXMock,
        folder_service: FolderService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test list() with OData filter parameter."""
        httpx_mock.add_response(
            json={
                "value": [
                    {
                        "Key": "folder-1",
                        "DisplayName": "Finance",
                        "FullyQualifiedName": "Shared/Finance",
                        "Id": 1,
                    }
                ]
            }
        )

        folders = list(folder_service.list(filter="DisplayName eq 'Finance'"))

        assert len(folders) == 1
        assert folders[0].display_name == "Finance"

        request = httpx_mock.get_request()
        assert request is not None
        assert "%24filter" in str(request.url) or "$filter" in str(request.url)

    def test_list_with_orderby(
        self,
        httpx_mock: HTTPXMock,
        folder_service: FolderService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test list() with OData orderby parameter."""
        httpx_mock.add_response(
            json={
                "value": [
                    {
                        "Key": "folder-1",
                        "DisplayName": "A-Folder",
                        "FullyQualifiedName": "Shared/A-Folder",
                        "Id": 1,
                    },
                    {
                        "Key": "folder-2",
                        "DisplayName": "B-Folder",
                        "FullyQualifiedName": "Shared/B-Folder",
                        "Id": 2,
                    },
                ]
            }
        )

        folders = list(folder_service.list(orderby="DisplayName asc"))

        assert len(folders) == 2

        request = httpx_mock.get_request()
        assert request is not None
        assert "%24orderby" in str(request.url) or "$orderby" in str(request.url)

    def test_exists_returns_true_when_folder_found(
        self,
        httpx_mock: HTTPXMock,
        folder_service: FolderService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test exists() returns True when folder is found."""
        httpx_mock.add_response(
            json={
                "value": [
                    {
                        "Key": "folder-key-123",
                        "DisplayName": "Finance",
                        "FullyQualifiedName": "Shared/Finance",
                        "Id": 1,
                    }
                ]
            }
        )

        exists = folder_service.exists(display_name="Finance")

        assert exists is True

    def test_exists_returns_false_when_folder_not_found(
        self,
        httpx_mock: HTTPXMock,
        folder_service: FolderService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test exists() returns False when folder not found."""
        httpx_mock.add_response(json={"value": []})

        exists = folder_service.exists(display_name="NonExistent")

        assert exists is False

    @pytest.mark.asyncio
    async def test_retrieve_async_by_key(
        self,
        httpx_mock: HTTPXMock,
        folder_service: FolderService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test retrieve_async() by key works identically to sync version."""
        httpx_mock.add_response(
            json={
                "value": [
                    {
                        "Key": "folder-key-async",
                        "DisplayName": "AsyncFolder",
                        "FullyQualifiedName": "Shared/AsyncFolder",
                        "Id": 1,
                    }
                ]
            }
        )

        folder = await folder_service.retrieve_async(key="folder-key-async")

        assert folder.key == "folder-key-async"
        assert folder.display_name == "AsyncFolder"

    @pytest.mark.asyncio
    async def test_list_async_paginates(
        self,
        httpx_mock: HTTPXMock,
        folder_service: FolderService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test list_async() paginates through folders."""
        # Mock first page
        httpx_mock.add_response(
            json={
                "value": [
                    {
                        "Key": "folder-1",
                        "DisplayName": "Folder1",
                        "FullyQualifiedName": "Shared/Folder1",
                        "Id": 1,
                    }
                ]
            }
        )

        folders = []
        async for folder in folder_service.list_async():
            folders.append(folder)

        assert len(folders) == 1
        assert folders[0].key == "folder-1"

    @pytest.mark.asyncio
    async def test_retrieve_async_by_display_name(
        self,
        httpx_mock: HTTPXMock,
        folder_service: FolderService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test retrieve_async() by display_name uses OData filter."""
        httpx_mock.add_response(
            json={
                "value": [
                    {
                        "Key": "folder-key-456",
                        "DisplayName": "AsyncFolder",
                        "FullyQualifiedName": "Shared/AsyncFolder",
                        "Id": 1,
                    }
                ]
            }
        )

        folder = await folder_service.retrieve_async(display_name="AsyncFolder")

        assert folder.key == "folder-key-456"
        assert folder.display_name == "AsyncFolder"

        # Verify OData filter was used
        request = httpx_mock.get_request()
        assert request is not None
        assert "%24filter" in str(request.url) or "$filter" in str(request.url)

    @pytest.mark.asyncio
    async def test_retrieve_by_path_async(
        self,
        httpx_mock: HTTPXMock,
        folder_service: FolderService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test retrieve_by_path_async() uses OData filter for path."""
        httpx_mock.add_response(
            json={
                "value": [
                    {
                        "Key": "folder-key-789",
                        "DisplayName": "Finance",
                        "FullyQualifiedName": "Shared/Finance/Invoices",
                        "Id": 1,
                    }
                ]
            }
        )

        folder = await folder_service.retrieve_by_path_async("Shared/Finance/Invoices")

        assert folder.fully_qualified_name == "Shared/Finance/Invoices"
        assert folder.key == "folder-key-789"

    @pytest.mark.asyncio
    async def test_exists_async_returns_true(
        self,
        httpx_mock: HTTPXMock,
        folder_service: FolderService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test exists_async() returns True when folder is found."""
        httpx_mock.add_response(
            json={
                "value": [
                    {
                        "Key": "folder-key-exists",
                        "DisplayName": "ExistingFolder",
                        "FullyQualifiedName": "Shared/ExistingFolder",
                        "Id": 1,
                    }
                ]
            }
        )

        exists = await folder_service.exists_async(display_name="ExistingFolder")

        assert exists is True

    @pytest.mark.asyncio
    async def test_exists_async_returns_false(
        self,
        httpx_mock: HTTPXMock,
        folder_service: FolderService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test exists_async() returns False when folder not found."""
        httpx_mock.add_response(json={"value": []})

        exists = await folder_service.exists_async(display_name="NonExistent")

        assert exists is False

    @pytest.mark.asyncio
    async def test_list_async_with_filter(
        self,
        httpx_mock: HTTPXMock,
        folder_service: FolderService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test list_async() with OData filter parameter."""
        httpx_mock.add_response(
            json={
                "value": [
                    {
                        "Key": "folder-filtered",
                        "DisplayName": "Finance",
                        "FullyQualifiedName": "Shared/Finance",
                        "Id": 1,
                    }
                ]
            }
        )

        folders = []
        async for folder in folder_service.list_async(
            filter="DisplayName eq 'Finance'"
        ):
            folders.append(folder)

        assert len(folders) == 1
        assert folders[0].display_name == "Finance"

        request = httpx_mock.get_request()
        assert request is not None
        assert "%24filter" in str(request.url) or "$filter" in str(request.url)

    @pytest.mark.asyncio
    async def test_retrieve_async_raises_lookup_error(
        self,
        httpx_mock: HTTPXMock,
        folder_service: FolderService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test retrieve_async() raises LookupError when folder not found."""
        httpx_mock.add_response(json={"value": []})

        with pytest.raises(
            LookupError, match="Folder with display_name 'NotFound' not found"
        ):
            await folder_service.retrieve_async(display_name="NotFound")

    def test_retrieve_with_key_and_display_name_prefers_key(
        self,
        httpx_mock: HTTPXMock,
        folder_service: FolderService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test retrieve() with both key and display_name uses key (key wins)."""
        # Mock response for key-based retrieval
        # Note: retrieve() with key iterates all folders, but we only return one
        httpx_mock.add_response(
            json={
                "value": [
                    {
                        "Key": "folder-key-123",
                        "DisplayName": "KeyFolder",
                        "FullyQualifiedName": "Shared/KeyFolder",
                        "Id": 1,
                    }
                ]
            }
        )

        # Provide BOTH key and display_name - key should win
        folder = folder_service.retrieve(
            key="folder-key-123", display_name="IgnoredDisplayName"
        )

        assert folder.key == "folder-key-123"
        assert folder.display_name == "KeyFolder"

        # Verify that the request used key-based retrieval (no $filter)
        request = httpx_mock.get_request()
        assert request is not None
        url_str = str(request.url)
        # When using key, there's no $filter for DisplayName
        # The implementation uses top=100 to paginate through all folders
        assert "$top" in url_str or "%24top" in url_str
        # Should NOT filter by DisplayName when key is provided
        assert "DisplayName" not in url_str
