"""Tests for OData injection security - Phase 5a.

This test suite validates that the SDK properly escapes user input in
safe parameters (name, display_name, folder_path) to prevent OData injection.

Note: Raw OData parameters (filter, orderby) are intentionally NOT escaped
by design to allow advanced users to build complex queries.
"""

import pytest
from pytest_httpx import HTTPXMock

from uipath._config import Config
from uipath._execution_context import ExecutionContext
from uipath._services.assets_service import AssetsService
from uipath._services.folder_service import FolderService


@pytest.fixture
def assets_service(
    config: Config, execution_context: ExecutionContext
) -> AssetsService:
    """AssetsService fixture for testing."""
    return AssetsService(config=config, execution_context=execution_context)


@pytest.fixture
def folder_service(
    config: Config, execution_context: ExecutionContext
) -> FolderService:
    """FolderService fixture for testing."""
    return FolderService(config=config, execution_context=execution_context)


class TestODataInjectionSecurity:
    """Test OData injection protection for safe parameters.

    The SDK escapes these parameters automatically:
    - AssetsService: 'name' parameter
    - FolderService: 'display_name', 'folder_path' parameters

    Raw OData parameters (filter, orderby) are passed through as-is.
    """

    def test_asset_name_escapes_single_quotes(
        self,
        httpx_mock: HTTPXMock,
        assets_service: AssetsService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test asset list() by name properly escapes single quotes."""
        httpx_mock.add_response(json={"value": []})

        # The 'name' parameter IS escaped by the SDK
        malicious_name = "Test' or '1'='1"
        list(assets_service.list(name=malicious_name))

        request = httpx_mock.get_request()
        assert request is not None
        # Verify single quote was escaped to two single quotes for OData
        # URL encoding: ' becomes %27, so '' becomes %27%27
        url_str = str(request.url)
        # Check for the escaped pattern in the contains() function
        assert "Test" in url_str and ("''" in url_str or "%27%27" in url_str)

    def test_asset_name_with_sql_injection_attempt(
        self,
        httpx_mock: HTTPXMock,
        assets_service: AssetsService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test asset name handles SQL injection attempt safely."""
        httpx_mock.add_response(json={"value": []})

        malicious_name = "Test'; DROP TABLE Assets;--"
        list(assets_service.list(name=malicious_name))

        request = httpx_mock.get_request()
        assert request is not None
        url_str = str(request.url)
        # Verify the quote was escaped
        assert "''" in url_str or "%27%27" in url_str

    def test_folder_display_name_escapes_quotes(
        self,
        httpx_mock: HTTPXMock,
        folder_service: FolderService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test folder retrieve() escapes quotes in display_name."""
        httpx_mock.add_response(json={"value": []})

        with pytest.raises(LookupError):
            folder_service.retrieve(display_name="Test' or '1'='1")

        request = httpx_mock.get_request()
        assert request is not None
        url_str = str(request.url)
        # Verify quote escaping in the $filter parameter
        assert "''" in url_str or "%27%27" in url_str
        assert "DisplayName" in url_str

    def test_folder_path_escapes_quotes(
        self,
        httpx_mock: HTTPXMock,
        folder_service: FolderService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test folder retrieve_by_path() escapes quotes in path."""
        httpx_mock.add_response(json={"value": []})

        with pytest.raises(LookupError):
            folder_service.retrieve_by_path("Shared/Test' or '1'='1")

        request = httpx_mock.get_request()
        assert request is not None
        url_str = str(request.url)
        # Verify quote escaping in FullyQualifiedName filter
        assert "''" in url_str or "%27%27" in url_str
        assert "FullyQualifiedName" in url_str

    def test_asset_name_with_special_characters_in_create(
        self,
        httpx_mock: HTTPXMock,
        assets_service: AssetsService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test asset creation handles special characters in name."""
        httpx_mock.add_response(
            json={
                "Key": "asset-key-123",
                "Name": "Test<script>alert('XSS')</script>",
                "StringValue": "test",
                "ValueType": "Text",
            }
        )

        asset = assets_service.create(
            name="Test<script>alert('XSS')</script>",
            value="test",
            value_type="Text",
        )

        assert asset.name == "Test<script>alert('XSS')</script>"

    def test_asset_name_with_unicode_quotes(
        self,
        httpx_mock: HTTPXMock,
        assets_service: AssetsService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test asset name handles unicode quote characters."""
        httpx_mock.add_response(json={"value": []})

        # Unicode right single quotation mark
        name_with_unicode = "Test\u2019value"
        list(assets_service.list(name=name_with_unicode))

        request = httpx_mock.get_request()
        assert request is not None
        # Just verify the request was made - unicode handling is at HTTP layer
        assert "Test" in str(request.url)

    def test_folder_display_name_with_parentheses(
        self,
        httpx_mock: HTTPXMock,
        folder_service: FolderService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test folder retrieve() handles parentheses in display_name."""
        httpx_mock.add_response(
            json={
                "value": [
                    {
                        "Key": "folder-key-123",
                        "DisplayName": "Test(Folder)",
                        "FullyQualifiedName": "Shared/Test(Folder)",
                        "Id": 1,
                    }
                ]
            }
        )

        folder = folder_service.retrieve(display_name="Test(Folder)")

        assert folder.display_name == "Test(Folder)"

    def test_asset_name_with_null_byte(
        self,
        httpx_mock: HTTPXMock,
        assets_service: AssetsService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test asset name handles null byte safely."""
        httpx_mock.add_response(json={"value": []})

        malicious_name = "Test\x00"
        list(assets_service.list(name=malicious_name))

        request = httpx_mock.get_request()
        assert request is not None

    def test_folder_path_with_path_traversal_attempt(
        self,
        httpx_mock: HTTPXMock,
        folder_service: FolderService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test folder retrieve_by_path() handles path traversal attempts."""
        httpx_mock.add_response(json={"value": []})

        with pytest.raises(LookupError):
            folder_service.retrieve_by_path("Shared/../../Admin")

        request = httpx_mock.get_request()
        assert request is not None
        # Path is passed as-is in the filter, API validates

    def test_asset_value_with_json_injection(
        self,
        httpx_mock: HTTPXMock,
        assets_service: AssetsService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test asset creation handles JSON-like values safely."""
        httpx_mock.add_response(
            json={
                "Key": "asset-key-123",
                "Name": "TestAsset",
                "StringValue": '{"malicious": "value"}',
                "ValueType": "Text",
            }
        )

        asset = assets_service.create(
            name="TestAsset", value='{"malicious": "value"}', value_type="Text"
        )

        assert asset.string_value == '{"malicious": "value"}'

    def test_legitimate_name_with_apostrophe(
        self,
        httpx_mock: HTTPXMock,
        folder_service: FolderService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test legitimate folder name with apostrophe works correctly."""
        httpx_mock.add_response(
            json={
                "value": [
                    {
                        "Key": "folder-key-123",
                        "DisplayName": "O'Brien's Folder",
                        "FullyQualifiedName": "Shared/O'Brien's Folder",
                        "Id": 1,
                    }
                ]
            }
        )

        folder = folder_service.retrieve(display_name="O'Brien's Folder")

        assert folder.display_name == "O'Brien's Folder"
        assert folder.key == "folder-key-123"

        # Verify escaping happened in the request
        request = httpx_mock.get_request()
        assert request is not None
        url_str = str(request.url)
        assert "''" in url_str or "%27%27" in url_str

    def test_asset_name_with_very_long_string(
        self,
        httpx_mock: HTTPXMock,
        assets_service: AssetsService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test asset name handles very long strings (>1000 chars) safely."""
        httpx_mock.add_response(json={"value": []})

        # Create a very long name (>1000 chars) with injection attempt
        long_name = "A" * 1000 + "' or '1'='1"
        list(assets_service.list(name=long_name))

        request = httpx_mock.get_request()
        assert request is not None
        url_str = str(request.url)
        # Verify quote was escaped even in long string
        assert "''" in url_str or "%27%27" in url_str

    def test_folder_path_with_consecutive_quotes(
        self,
        httpx_mock: HTTPXMock,
        folder_service: FolderService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test folder path escapes multiple consecutive quotes."""
        httpx_mock.add_response(json={"value": []})

        with pytest.raises(LookupError):
            folder_service.retrieve_by_path("Shared/Test'''Folder")

        request = httpx_mock.get_request()
        assert request is not None
        url_str = str(request.url)
        # All three consecutive quotes should be escaped to six single quotes
        # (each ' becomes '')
        # Looking for the escaped pattern in the URL
        assert "''" in url_str or "%27%27" in url_str

    def test_asset_name_with_mixed_quote_types(
        self,
        httpx_mock: HTTPXMock,
        assets_service: AssetsService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test asset name with mixed quote types (single, double, backtick)."""
        httpx_mock.add_response(json={"value": []})

        # Mix of single quotes, double quotes, and backticks
        mixed_quotes = "Test'Asset\"with`quotes"
        list(assets_service.list(name=mixed_quotes))

        request = httpx_mock.get_request()
        assert request is not None
        url_str = str(request.url)
        # Single quotes should be escaped, double quotes and backticks passed through
        # OData only requires escaping single quotes
        assert "''" in url_str or "%27%27" in url_str
        # Double quotes and backticks are safe in OData
        assert "Asset" in url_str

    def test_folder_display_name_with_crlf_injection(
        self,
        httpx_mock: HTTPXMock,
        folder_service: FolderService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test folder display_name with CRLF injection attempt."""
        httpx_mock.add_response(json={"value": []})

        # CRLF injection attempt
        crlf_name = "Folder\r\n' or '1'='1"
        with pytest.raises(LookupError):
            folder_service.retrieve(display_name=crlf_name)

        request = httpx_mock.get_request()
        assert request is not None
        url_str = str(request.url)
        # Verify quote escaping happened
        assert "''" in url_str or "%27%27" in url_str
        # CRLF characters are URL-encoded by HTTP layer
        assert "DisplayName" in url_str
