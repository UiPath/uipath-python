"""Test pagination limit behavior for BucketService.

Tests cover all edge cases identified in code review:
- Pagination limit reached with full pages
- Pagination limit reached with partial last page
- Successful completion under limit
- Empty result sets
- Both sync and async variants
- All three pagination methods (offset, token, glob)
"""

from unittest.mock import MagicMock

import pytest

from uipath.models import PaginationLimitError


class TestOffsetPaginationLimits:
    """Test offset-based pagination (list, list_async)."""

    def test_list_pagination_limit_with_full_pages(
        self, config, execution_context, monkeypatch
    ):
        """Test that list() raises PaginationLimitError after MAX_PAGES with full pages."""
        from uipath._services.buckets_service import BucketsService

        service = BucketsService(config=config, execution_context=execution_context)

        # Mock request to always return full pages
        def mock_request(*args, **kwargs):
            response = MagicMock()
            response.json.return_value = {
                "value": [
                    {"Id": i, "Name": f"bucket-{i}", "Identifier": f"bucket-{i}"}
                    for i in range(100)
                ]
            }
            return response

        monkeypatch.setattr(service, "request", mock_request)

        # Should hit limit after 10 pages
        with pytest.raises(PaginationLimitError) as exc_info:
            list(service.list())

        message = str(exc_info.value)
        assert "10 pages (1000 items)" in message
        assert "name=" in message
        assert "Add filters to narrow your query" in message

    def test_list_no_error_when_under_limit(
        self, config, execution_context, monkeypatch
    ):
        """Test that list() completes successfully when under pagination limit."""
        from uipath._services.buckets_service import BucketsService

        service = BucketsService(config=config, execution_context=execution_context)

        # Return 3 pages, then empty
        call_count = 0

        def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            response = MagicMock()
            if call_count <= 3:
                response.json.return_value = {
                    "value": [
                        {
                            "Id": i,
                            "Name": f"bucket-{call_count}-{i}",
                            "Identifier": f"bucket-{call_count}-{i}",
                        }
                        for i in range(100)
                    ]
                }
            else:
                response.json.return_value = {"value": []}
            return response

        monkeypatch.setattr(service, "request", mock_request)

        results = list(service.list())
        assert len(results) == 300  # 3 pages × 100 items

    def test_list_with_partial_last_page_under_limit(
        self, config, execution_context, monkeypatch
    ):
        """Test list() with partial last page under limit completes successfully."""
        from uipath._services.buckets_service import BucketsService

        service = BucketsService(config=config, execution_context=execution_context)

        call_count = 0

        def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            response = MagicMock()
            if call_count < 3:
                # Full pages
                response.json.return_value = {
                    "value": [
                        {"Id": i, "Name": f"bucket-{i}", "Identifier": f"bucket-{i}"}
                        for i in range(100)
                    ]
                }
            elif call_count == 3:
                # Partial last page
                response.json.return_value = {
                    "value": [
                        {"Id": i, "Name": f"bucket-{i}", "Identifier": f"bucket-{i}"}
                        for i in range(73)
                    ]
                }
            else:
                response.json.return_value = {"value": []}
            return response

        monkeypatch.setattr(service, "request", mock_request)

        results = list(service.list())
        assert len(results) == 273  # 200 + 73

    def test_list_empty_results(self, config, execution_context, monkeypatch):
        """Test list() with empty results."""
        from uipath._services.buckets_service import BucketsService

        service = BucketsService(config=config, execution_context=execution_context)

        def mock_request(*args, **kwargs):
            response = MagicMock()
            response.json.return_value = {"value": []}
            return response

        monkeypatch.setattr(service, "request", mock_request)

        results = list(service.list())
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_list_async_pagination_limit(
        self, config, execution_context, monkeypatch
    ):
        """Test that list_async() raises PaginationLimitError after MAX_PAGES."""
        from uipath._services.buckets_service import BucketsService

        service = BucketsService(config=config, execution_context=execution_context)

        async def mock_request_async(*args, **kwargs):
            response = MagicMock()
            response.json.return_value = {
                "value": [
                    {"Id": i, "Name": f"bucket-{i}", "Identifier": f"bucket-{i}"}
                    for i in range(50)
                ]
            }
            return response

        monkeypatch.setattr(service, "request_async", mock_request_async)

        with pytest.raises(PaginationLimitError) as exc_info:
            results = []
            async for bucket in service.list_async():
                results.append(bucket)

        assert "10 pages (500 items)" in str(exc_info.value)


class TestTokenPaginationLimits:
    """Test continuation token-based pagination (list_files, list_files_async)."""

    def test_list_files_pagination_limit(self, config, execution_context, monkeypatch):
        """Test that list_files() raises PaginationLimitError after MAX_PAGES."""
        from uipath._services.buckets_service import BucketsService

        service = BucketsService(config=config, execution_context=execution_context)

        def mock_retrieve(*args, **kwargs):
            return MagicMock(id=123, name="test-bucket")

        call_count = 0

        def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            response = MagicMock()
            response.json.return_value = {
                "items": [
                    {"fullPath": f"/file-{call_count}-{i}", "size": 100}
                    for i in range(500)
                ],
                # Always return a token to trigger pagination limit
                "continuationToken": f"token-{call_count}",
            }
            return response

        monkeypatch.setattr(service, "retrieve", mock_retrieve)
        monkeypatch.setattr(service, "request", mock_request)

        with pytest.raises(PaginationLimitError) as exc_info:
            list(service.list_files(name="test-bucket"))

        message = str(exc_info.value)
        assert "10 pages" in message
        assert "prefix=" in message
        assert "Add filters to narrow your query" in message

    @pytest.mark.asyncio
    async def test_list_files_async_pagination_limit(
        self, config, execution_context, monkeypatch
    ):
        """Test that list_files_async() raises PaginationLimitError after MAX_PAGES."""
        from uipath._services.buckets_service import BucketsService

        service = BucketsService(config=config, execution_context=execution_context)

        async def mock_retrieve_async(*args, **kwargs):
            return MagicMock(id=123, name="test-bucket")

        call_count = 0

        async def mock_request_async(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            response = MagicMock()
            response.json.return_value = {
                "items": [
                    {"fullPath": f"/file-{call_count}-{i}", "size": 100}
                    for i in range(500)
                ],
                # Always return a token to trigger pagination limit
                "continuationToken": f"token-{call_count}",
            }
            return response

        monkeypatch.setattr(service, "retrieve_async", mock_retrieve_async)
        monkeypatch.setattr(service, "request_async", mock_request_async)

        with pytest.raises(PaginationLimitError) as exc_info:
            results = []
            async for file in service.list_files_async(name="test-bucket"):
                results.append(file)

        assert "10 pages" in str(exc_info.value)

    def test_list_files_completes_when_token_becomes_none(
        self, config, execution_context, monkeypatch
    ):
        """Test list_files() completes successfully when token becomes None."""
        from uipath._services.buckets_service import BucketsService

        service = BucketsService(config=config, execution_context=execution_context)

        def mock_retrieve(*args, **kwargs):
            return MagicMock(id=123, name="test-bucket")

        call_count = 0

        def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            response = MagicMock()
            if call_count < 5:
                response.json.return_value = {
                    "items": [
                        {"fullPath": f"/file-{i}", "size": 100} for i in range(500)
                    ],
                    "continuationToken": f"token-{call_count}",
                }
            else:
                # Last page with no token
                response.json.return_value = {
                    "items": [
                        {"fullPath": f"/file-{i}", "size": 100} for i in range(250)
                    ],
                    "continuationToken": None,
                }
            return response

        monkeypatch.setattr(service, "retrieve", mock_retrieve)
        monkeypatch.setattr(service, "request", mock_request)

        results = list(service.list_files(name="test-bucket"))
        assert len(results) == 2250  # 4*500 + 250


class TestGlobPaginationLimits:
    """Test glob pattern-based pagination (get_files, get_files_async)."""

    def test_get_files_pagination_limit(self, config, execution_context, monkeypatch):
        """Test that get_files() raises PaginationLimitError after MAX_PAGES."""
        from uipath._services.buckets_service import BucketsService

        service = BucketsService(config=config, execution_context=execution_context)

        def mock_retrieve(*args, **kwargs):
            return MagicMock(id=123, name="test-bucket")

        def mock_request(*args, **kwargs):
            response = MagicMock()
            response.json.return_value = {
                "value": [
                    {"fullPath": f"/file-{i}", "size": 100, "IsDirectory": False}
                    for i in range(500)
                ]
            }
            return response

        monkeypatch.setattr(service, "retrieve", mock_retrieve)
        monkeypatch.setattr(service, "request", mock_request)

        with pytest.raises(PaginationLimitError) as exc_info:
            list(service.get_files(name="test-bucket"))

        message = str(exc_info.value)
        assert "10 pages (5000 items)" in message
        assert "file_name_glob=" in message or "prefix=" in message
        assert "Add filters to narrow your query" in message

    @pytest.mark.asyncio
    async def test_get_files_async_pagination_limit(
        self, config, execution_context, monkeypatch
    ):
        """Test that get_files_async() raises PaginationLimitError after MAX_PAGES."""
        from uipath._services.buckets_service import BucketsService

        service = BucketsService(config=config, execution_context=execution_context)

        async def mock_retrieve_async(*args, **kwargs):
            return MagicMock(id=123, name="test-bucket")

        async def mock_request_async(*args, **kwargs):
            response = MagicMock()
            response.json.return_value = {
                "value": [
                    {"fullPath": f"/file-{i}", "size": 100, "IsDirectory": False}
                    for i in range(500)
                ]
            }
            return response

        monkeypatch.setattr(service, "retrieve_async", mock_retrieve_async)
        monkeypatch.setattr(service, "request_async", mock_request_async)

        with pytest.raises(PaginationLimitError) as exc_info:
            results = []
            async for file in service.get_files_async(name="test-bucket"):
                results.append(file)

        assert "10 pages" in str(exc_info.value)

    def test_get_files_filters_directories(
        self, config, execution_context, monkeypatch
    ):
        """Test that get_files() filters out directories."""
        from uipath._services.buckets_service import BucketsService

        service = BucketsService(config=config, execution_context=execution_context)

        def mock_retrieve(*args, **kwargs):
            return MagicMock(id=123, name="test-bucket")

        call_count = 0

        def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            response = MagicMock()
            if call_count == 1:
                response.json.return_value = {
                    "value": [
                        {"fullPath": "/dir1", "size": 0, "IsDirectory": True},
                        {"fullPath": "/file1", "size": 100, "IsDirectory": False},
                        {"fullPath": "/dir2", "size": 0, "IsDirectory": True},
                        {"fullPath": "/file2", "size": 200, "IsDirectory": False},
                    ]
                }
            else:
                response.json.return_value = {"value": []}
            return response

        monkeypatch.setattr(service, "retrieve", mock_retrieve)
        monkeypatch.setattr(service, "request", mock_request)

        results = list(service.get_files(name="test-bucket"))
        assert len(results) == 2  # Only files, not directories


class TestErrorMessageFormats:
    """Test that error messages are correctly formatted for each pagination type."""

    def test_offset_pagination_error_format(self):
        """Test offset pagination error message format."""
        error = PaginationLimitError.create(
            max_pages=10,
            items_per_page=100,
            method_name="list",
            filter_example='name="my-bucket"',
        )

        message = str(error)
        assert "10 pages (1000 items)" in message
        assert 'list(name="my-bucket")' in message
        assert "Add filters to narrow your query" in message
        assert "https://docs.uipath.com/orchestrator" in message

    def test_token_pagination_error_format(self):
        """Test token pagination error message format."""
        error = PaginationLimitError.create(
            max_pages=10,
            items_per_page=500,
            method_name="list_files",
            filter_example='prefix="data/"',
        )

        message = str(error)
        assert "10 pages (5000 items)" in message
        assert 'list_files(prefix="data/")' in message
        assert "Add filters to narrow your query" in message

    def test_glob_pagination_error_format(self):
        """Test glob pagination error message format."""
        error = PaginationLimitError.create(
            max_pages=10,
            items_per_page=500,
            method_name="get_files",
            filter_example='file_name_glob="*.pdf"',
        )

        message = str(error)
        assert "10 pages (5000 items)" in message
        assert 'get_files(file_name_glob="*.pdf")' in message
        assert "Add filters to narrow your query" in message
