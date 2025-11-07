import os
from pathlib import Path

import pytest
from pytest_httpx import HTTPXMock

from uipath._config import Config
from uipath._execution_context import ExecutionContext
from uipath._services.buckets_service import BucketsService


@pytest.fixture
def service(
    config: Config, execution_context: ExecutionContext, monkeypatch: pytest.MonkeyPatch
) -> BucketsService:
    monkeypatch.setenv("UIPATH_FOLDER_PATH", "test-folder-path")
    return BucketsService(config=config, execution_context=execution_context)


@pytest.fixture
def temp_file(tmp_path):
    """Create a temporary file for testing."""
    file_path = tmp_path / "test.txt"
    file_path.write_text("test content")
    return str(file_path)


class TestBucketsService:
    class TestRetrieve:
        def test_retrieve_by_key(
            self,
            httpx_mock: HTTPXMock,
            service: BucketsService,
            base_url: str,
            org: str,
            tenant: str,
        ):
            bucket_key = "bucket-key"
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets/UiPath.Server.Configuration.OData.GetByKey(identifier='{bucket_key}')",
                status_code=200,
                json={
                    "value": [
                        {"Id": 123, "Name": "test-bucket", "Identifier": "bucket-key"}
                    ]
                },
            )

            bucket = service.retrieve(key=bucket_key)
            assert bucket.id == 123
            assert bucket.name == "test-bucket"
            assert bucket.identifier == "bucket-key"

        def test_retrieve_by_name(
            self,
            httpx_mock: HTTPXMock,
            service: BucketsService,
            base_url: str,
            org: str,
            tenant: str,
        ):
            bucket_name = "test-bucket"
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets?$filter=Name eq '{bucket_name}'&$top=1",
                status_code=200,
                json={
                    "value": [
                        {"Id": 123, "Name": "test-bucket", "Identifier": "bucket-key"}
                    ]
                },
            )

            bucket = service.retrieve(name=bucket_name)
            assert bucket.id == 123
            assert bucket.name == "test-bucket"
            assert bucket.identifier == "bucket-key"

        @pytest.mark.asyncio
        async def test_retrieve_by_key_async(
            self,
            httpx_mock: HTTPXMock,
            service: BucketsService,
            base_url: str,
            org: str,
            tenant: str,
        ):
            bucket_key = "bucket-key"
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets/UiPath.Server.Configuration.OData.GetByKey(identifier='{bucket_key}')",
                status_code=200,
                json={
                    "value": [
                        {"Id": 123, "Name": "test-bucket", "Identifier": "bucket-key"}
                    ]
                },
            )

            bucket = await service.retrieve_async(key=bucket_key)
            assert bucket.id == 123
            assert bucket.name == "test-bucket"
            assert bucket.identifier == "bucket-key"

        @pytest.mark.asyncio
        async def test_retrieve_by_name_async(
            self,
            httpx_mock: HTTPXMock,
            service: BucketsService,
            base_url: str,
            org: str,
            tenant: str,
        ):
            bucket_name = "test-bucket"
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets?$filter=Name eq '{bucket_name}'&$top=1",
                status_code=200,
                json={
                    "value": [
                        {"Id": 123, "Name": "test-bucket", "Identifier": "bucket-key"}
                    ]
                },
            )

            bucket = await service.retrieve_async(name=bucket_name)
            assert bucket.id == 123
            assert bucket.name == "test-bucket"
            assert bucket.identifier == "bucket-key"

    class TestDownload:
        def test_download(
            self,
            httpx_mock: HTTPXMock,
            service: BucketsService,
            base_url: str,
            org: str,
            tenant: str,
            tmp_path: Path,
        ):
            bucket_key = "bucket-key"
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets/UiPath.Server.Configuration.OData.GetByKey(identifier='{bucket_key}')",
                status_code=200,
                json={
                    "value": [
                        {"Id": 123, "Name": "test-bucket", "Identifier": "bucket-key"}
                    ]
                },
            )

            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets(123)/UiPath.Server.Configuration.OData.GetReadUri?path=test-file.txt",
                status_code=200,
                json={
                    "Uri": "https://test-storage.com/test-file.txt",
                    "Headers": {"Keys": [], "Values": []},
                    "RequiresAuth": False,
                },
            )

            httpx_mock.add_response(
                url="https://test-storage.com/test-file.txt",
                status_code=200,
                content=b"test content",
            )

            destination_path = str(tmp_path / "downloaded.txt")
            service.download(
                key=bucket_key,
                blob_file_path="test-file.txt",
                destination_path=destination_path,
            )

            assert os.path.exists(destination_path)
            with open(destination_path, "rb") as f:
                assert f.read() == b"test content"

    class TestUpload:
        def test_upload_from_path(
            self,
            httpx_mock: HTTPXMock,
            service: BucketsService,
            base_url: str,
            org: str,
            tenant: str,
            temp_file: str,
        ):
            bucket_key = "bucket-key"
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets/UiPath.Server.Configuration.OData.GetByKey(identifier='{bucket_key}')",
                status_code=200,
                json={
                    "value": [
                        {"Id": 123, "Name": "test-bucket", "Identifier": "bucket-key"}
                    ]
                },
            )

            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets(123)/UiPath.Server.Configuration.OData.GetWriteUri?path=test-file.txt&contentType=text/plain",
                status_code=200,
                json={
                    "Uri": "https://test-storage.com/test-file.txt",
                    "Headers": {"Keys": [], "Values": []},
                    "RequiresAuth": False,
                },
            )

            httpx_mock.add_response(
                url="https://test-storage.com/test-file.txt",
                status_code=200,
                content=b"test content",
            )

            service.upload(
                key=bucket_key,
                blob_file_path="test-file.txt",
                content_type="text/plain",
                source_path=temp_file,
            )

            sent_requests = httpx_mock.get_requests()
            assert len(sent_requests) == 3

            assert sent_requests[2].method == "PUT"
            assert sent_requests[2].url == "https://test-storage.com/test-file.txt"

            assert b"test content" in sent_requests[2].content

        def test_upload_from_memory(
            self,
            httpx_mock: HTTPXMock,
            service: BucketsService,
            base_url: str,
            org: str,
            tenant: str,
        ):
            bucket_key = "bucket-key"
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets/UiPath.Server.Configuration.OData.GetByKey(identifier='{bucket_key}')",
                status_code=200,
                json={
                    "value": [
                        {"Id": 123, "Name": "test-bucket", "Identifier": "bucket-key"}
                    ]
                },
            )

            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets(123)/UiPath.Server.Configuration.OData.GetWriteUri?path=test-file.txt&contentType=text/plain",
                status_code=200,
                json={
                    "Uri": "https://test-storage.com/test-file.txt",
                    "Headers": {"Keys": [], "Values": []},
                    "RequiresAuth": False,
                },
            )

            httpx_mock.add_response(
                url="https://test-storage.com/test-file.txt",
                status_code=200,
                content=b"test content",
            )

            service.upload(
                key=bucket_key,
                blob_file_path="test-file.txt",
                content_type="text/plain",
                content="test content",
            )

            sent_requests = httpx_mock.get_requests()
            assert len(sent_requests) == 3

            assert sent_requests[2].method == "PUT"
            assert sent_requests[2].url == "https://test-storage.com/test-file.txt"
            assert sent_requests[2].content == b"test content"


class TestList:
    """Tests for list() method with auto-pagination."""

    def test_list_all_buckets(
        self,
        httpx_mock: HTTPXMock,
        service: BucketsService,
        base_url: str,
        org: str,
        tenant: str,
    ):
        """Test listing all buckets with auto-pagination."""
        # Mock first page (100 items - full page)
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets?$skip=0&$top=100",
            status_code=200,
            json={
                "value": [
                    {"Id": i, "Name": f"bucket-{i}", "Identifier": f"id-{i}"}
                    for i in range(100)
                ]
            },
        )
        # Mock second page (30 items - partial page signals end)
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets?$skip=100&$top=100",
            status_code=200,
            json={
                "value": [
                    {"Id": i, "Name": f"bucket-{i}", "Identifier": f"id-{i}"}
                    for i in range(100, 130)
                ]
            },
        )

        buckets = list(service.list())
        assert len(buckets) == 130
        assert buckets[0].id == 0
        assert buckets[129].id == 129

    def test_list_with_name_filter(
        self,
        httpx_mock: HTTPXMock,
        service: BucketsService,
        base_url: str,
        org: str,
        tenant: str,
    ):
        """Test filtering by bucket name."""
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets?$skip=0&$top=100&$filter=contains%28tolower%28Name%29%2C+tolower%28%27test%27%29%29",
            status_code=200,
            json={
                "value": [
                    {"Id": 1, "Name": "test-bucket", "Identifier": "id-1"},
                    {"Id": 2, "Name": "another-test", "Identifier": "id-2"},
                ]
            },
        )

        buckets = list(service.list(name="test"))
        assert len(buckets) == 2
        assert buckets[0].name == "test-bucket"

    def test_list_with_folder_path(
        self,
        httpx_mock: HTTPXMock,
        service: BucketsService,
        base_url: str,
        org: str,
        tenant: str,
    ):
        """Test listing with folder context."""
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets?$skip=0&$top=100",
            status_code=200,
            json={"value": [{"Id": 1, "Name": "bucket-1", "Identifier": "id-1"}]},
            match_headers={"x-uipath-folderpath": "Production"},
        )

        buckets = list(service.list(folder_path="Production"))
        assert len(buckets) == 1

    def test_list_empty_results(
        self,
        httpx_mock: HTTPXMock,
        service: BucketsService,
        base_url: str,
        org: str,
        tenant: str,
    ):
        """Test list() with no buckets."""
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets?$skip=0&$top=100",
            status_code=200,
            json={"value": []},
        )

        buckets = list(service.list())
        assert len(buckets) == 0

    def test_list_pagination_stops_on_partial_page(
        self,
        httpx_mock: HTTPXMock,
        service: BucketsService,
        base_url: str,
        org: str,
        tenant: str,
    ):
        """Test pagination stops when fewer items than page size."""
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets?$skip=0&$top=100",
            status_code=200,
            json={
                "value": [
                    {"Id": i, "Name": f"bucket-{i}", "Identifier": f"id-{i}"}
                    for i in range(30)
                ]
            },
        )

        buckets = list(service.list())
        assert len(buckets) == 30
        # Verify only one request was made (no pagination)
        assert len(httpx_mock.get_requests()) == 1

    @pytest.mark.asyncio
    async def test_list_async(
        self,
        httpx_mock: HTTPXMock,
        service: BucketsService,
        base_url: str,
        org: str,
        tenant: str,
    ):
        """Test async version of list()."""
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets?$skip=0&$top=50",
            status_code=200,
            json={
                "value": [
                    {"Id": i, "Name": f"bucket-{i}", "Identifier": f"id-{i}"}
                    for i in range(10)
                ]
            },
        )

        buckets = []
        async for bucket in service.list_async():
            buckets.append(bucket)

        assert len(buckets) == 10


class TestExists:
    """Tests for exists() method."""

    def test_exists_bucket_found(
        self,
        httpx_mock: HTTPXMock,
        service: BucketsService,
        base_url: str,
        org: str,
        tenant: str,
    ):
        """Test exists() returns True when bucket found."""
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets?$filter=Name eq 'test-bucket'&$top=1",
            status_code=200,
            json={"value": [{"Id": 1, "Name": "test-bucket", "Identifier": "id-1"}]},
        )

        assert service.exists("test-bucket") is True

    def test_exists_bucket_not_found(
        self,
        httpx_mock: HTTPXMock,
        service: BucketsService,
        base_url: str,
        org: str,
        tenant: str,
    ):
        """Test exists() returns False for LookupError."""
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets?$filter=Name eq 'nonexistent'&$top=1",
            status_code=200,
            json={"value": []},
        )

        assert service.exists("nonexistent") is False

    def test_exists_propagates_network_errors(
        self,
        httpx_mock: HTTPXMock,
        service: BucketsService,
        base_url: str,
        org: str,
        tenant: str,
    ):
        """Test exists() propagates non-LookupError exceptions."""
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets?$filter=Name eq 'error-bucket'&$top=1",
            status_code=500,
        )

        # Should raise exception (not return False)
        from uipath.models.exceptions import EnrichedException

        with pytest.raises(EnrichedException):
            service.exists("error-bucket")

    @pytest.mark.asyncio
    async def test_exists_async(
        self,
        httpx_mock: HTTPXMock,
        service: BucketsService,
        base_url: str,
        org: str,
        tenant: str,
    ):
        """Test async version of exists()."""
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets?$filter=Name eq 'async-bucket'&$top=1",
            status_code=200,
            json={"value": [{"Id": 1, "Name": "async-bucket", "Identifier": "id-1"}]},
        )

        result = await service.exists_async("async-bucket")
        assert result is True


class TestCreate:
    """Tests for create() method."""

    def test_create_with_auto_uuid(
        self,
        httpx_mock: HTTPXMock,
        service: BucketsService,
        base_url: str,
        org: str,
        tenant: str,
    ):
        """Test create() auto-generates UUID if not provided."""
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets",
            status_code=201,
            json={"Id": 1, "Name": "new-bucket", "Identifier": "auto-uuid-123"},
            match_content=None,  # We'll check the request separately
        )

        bucket = service.create("new-bucket")
        assert bucket.id == 1
        assert bucket.name == "new-bucket"

        # Verify UUID was in request
        requests = httpx_mock.get_requests()
        assert len(requests) == 1
        import json

        body = json.loads(requests[0].content)
        assert "Identifier" in body
        assert len(body["Identifier"]) > 0  # UUID generated

    def test_create_with_explicit_uuid(
        self,
        httpx_mock: HTTPXMock,
        service: BucketsService,
        base_url: str,
        org: str,
        tenant: str,
    ):
        """Test create() uses provided UUID."""
        custom_uuid = "custom-uuid-456"
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets",
            status_code=201,
            json={
                "Id": 1,
                "Name": "new-bucket",
                "Identifier": custom_uuid,
            },
        )

        bucket = service.create("new-bucket", identifier=custom_uuid)
        assert bucket.identifier == custom_uuid

        # Verify exact UUID in request
        requests = httpx_mock.get_requests()
        import json

        body = json.loads(requests[0].content)
        assert body["Identifier"] == custom_uuid

    def test_create_with_description(
        self,
        httpx_mock: HTTPXMock,
        service: BucketsService,
        base_url: str,
        org: str,
        tenant: str,
    ):
        """Test create() includes description."""
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets",
            status_code=201,
            json={
                "Id": 1,
                "Name": "new-bucket",
                "Identifier": "id-1",
                "Description": "Test description",
            },
        )

        service.create("new-bucket", description="Test description")

        # Verify Description field in request body
        requests = httpx_mock.get_requests()
        import json

        body = json.loads(requests[0].content)
        assert body["Description"] == "Test description"

    def test_create_with_folder_context(
        self,
        httpx_mock: HTTPXMock,
        service: BucketsService,
        base_url: str,
        org: str,
        tenant: str,
    ):
        """Test create() with folder_path."""
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets",
            status_code=201,
            json={"Id": 1, "Name": "new-bucket", "Identifier": "id-1"},
            match_headers={"x-uipath-folderpath": "Production"},
        )

        bucket = service.create("new-bucket", folder_path="Production")
        assert bucket.id == 1

    def test_create_name_escaping(
        self,
        httpx_mock: HTTPXMock,
        service: BucketsService,
        base_url: str,
        org: str,
        tenant: str,
    ):
        """Test bucket names with special chars don't break creation."""
        bucket_name = "Test's Bucket"
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets",
            status_code=201,
            json={"Id": 1, "Name": bucket_name, "Identifier": "id-1"},
        )

        bucket = service.create(bucket_name)
        assert bucket.name == bucket_name

    @pytest.mark.asyncio
    async def test_create_async(
        self,
        httpx_mock: HTTPXMock,
        service: BucketsService,
        base_url: str,
        org: str,
        tenant: str,
    ):
        """Test async version of create()."""
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets",
            status_code=201,
            json={"Id": 1, "Name": "async-bucket", "Identifier": "id-1"},
        )

        bucket = await service.create_async("async-bucket")
        assert bucket.id == 1


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_retrieve_with_quotes_in_name(
        self,
        httpx_mock: HTTPXMock,
        service: BucketsService,
        base_url: str,
        org: str,
        tenant: str,
    ):
        """Test bucket name with single quotes (OData escaping)."""
        bucket_name = "Test's Bucket"
        escaped_name = "Test''s Bucket"  # OData escaping

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets?$filter=Name eq '{escaped_name}'&$top=1",
            status_code=200,
            json={"value": [{"Id": 1, "Name": bucket_name, "Identifier": "id-1"}]},
        )

        bucket = service.retrieve(name=bucket_name)
        assert bucket.name == bucket_name

    def test_retrieve_key_not_found(
        self,
        httpx_mock: HTTPXMock,
        service: BucketsService,
        base_url: str,
        org: str,
        tenant: str,
    ):
        """Test retrieve by key raises LookupError."""
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets/UiPath.Server.Configuration.OData.GetByKey(identifier='nonexistent')",
            status_code=200,
            json={"value": []},
        )

        with pytest.raises(LookupError, match="key 'nonexistent' not found"):
            service.retrieve(key="nonexistent")

    def test_retrieve_name_not_found(
        self,
        httpx_mock: HTTPXMock,
        service: BucketsService,
        base_url: str,
        org: str,
        tenant: str,
    ):
        """Test retrieve by name raises LookupError."""
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets?$filter=Name eq 'nonexistent'&$top=1",
            status_code=200,
            json={"value": []},
        )

        with pytest.raises(LookupError, match="name 'nonexistent' not found"):
            service.retrieve(name="nonexistent")

    def test_list_handles_odata_collection_wrapper(
        self,
        httpx_mock: HTTPXMock,
        service: BucketsService,
        base_url: str,
        org: str,
        tenant: str,
    ):
        """Test list() handles OData 'value' array correctly."""
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets?$skip=0&$top=100",
            status_code=200,
            json={
                "value": [{"Id": 1, "Name": "bucket-1", "Identifier": "id-1"}],
                "@odata.context": "https://example.com/$metadata#Buckets",
            },
        )

        buckets = list(service.list())
        assert len(buckets) == 1
        assert buckets[0].id == 1


class TestListFiles:
    """Tests for list_files() method (REST ListFiles API)."""

    def test_list_files_basic(
        self,
        httpx_mock: HTTPXMock,
        service: BucketsService,
        base_url: str,
        org: str,
        tenant: str,
    ):
        """Test basic file listing with list_files()."""
        # Mock bucket retrieve
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets?$filter=Name eq 'test-bucket'&$top=1",
            status_code=200,
            json={"value": [{"Id": 123, "Name": "test-bucket", "Identifier": "id-1"}]},
        )

        # Mock ListFiles response
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/api/Buckets/123/ListFiles?takeHint=500",
            status_code=200,
            json={
                "items": [
                    {
                        "fullPath": "/data/file1.txt",
                        "contentType": "text/plain",
                        "size": 100,
                        "lastModified": "2024-01-01T00:00:00Z",
                    },
                    {
                        "fullPath": "/data/file2.txt",
                        "contentType": "text/plain",
                        "size": 200,
                        "lastModified": "2024-01-02T00:00:00Z",
                    },
                ],
                "continuationToken": None,
            },
        )

        files = list(service.list_files(name="test-bucket"))
        assert len(files) == 2
        assert files[0].path == "/data/file1.txt"
        assert files[0].size == 100
        assert files[1].path == "/data/file2.txt"
        assert files[1].size == 200

    def test_list_files_with_prefix(
        self,
        httpx_mock: HTTPXMock,
        service: BucketsService,
        base_url: str,
        org: str,
        tenant: str,
    ):
        """Test list_files() with prefix filter."""
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets?$filter=Name eq 'test-bucket'&$top=1",
            status_code=200,
            json={"value": [{"Id": 123, "Name": "test-bucket", "Identifier": "id-1"}]},
        )

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/api/Buckets/123/ListFiles?prefix=data&takeHint=500",
            status_code=200,
            json={
                "items": [
                    {
                        "fullPath": "/data/file1.txt",
                        "contentType": "text/plain",
                        "size": 100,
                        "lastModified": "2024-01-01T00:00:00Z",
                    }
                ],
                "continuationToken": None,
            },
        )

        files = list(service.list_files(name="test-bucket", prefix="data"))
        assert len(files) == 1
        assert files[0].path == "/data/file1.txt"

    def test_list_files_pagination(
        self,
        httpx_mock: HTTPXMock,
        service: BucketsService,
        base_url: str,
        org: str,
        tenant: str,
    ):
        """Test list_files() handles pagination with continuationToken."""
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets?$filter=Name eq 'test-bucket'&$top=1",
            status_code=200,
            json={"value": [{"Id": 123, "Name": "test-bucket", "Identifier": "id-1"}]},
        )

        # First page
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/api/Buckets/123/ListFiles?takeHint=500",
            status_code=200,
            json={
                "items": [
                    {
                        "fullPath": f"/file{i}.txt",
                        "contentType": "text/plain",
                        "size": 100,
                        "lastModified": "2024-01-01T00:00:00Z",
                    }
                    for i in range(500)
                ],
                "continuationToken": "page2token",
            },
        )

        # Second page
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/api/Buckets/123/ListFiles?continuationToken=page2token&takeHint=500",
            status_code=200,
            json={
                "items": [
                    {
                        "fullPath": f"/file{i}.txt",
                        "contentType": "text/plain",
                        "size": 100,
                        "lastModified": "2024-01-01T00:00:00Z",
                    }
                    for i in range(500, 550)
                ],
                "continuationToken": None,
            },
        )

        files = list(service.list_files(name="test-bucket"))
        assert len(files) == 550

    def test_list_files_empty(
        self,
        httpx_mock: HTTPXMock,
        service: BucketsService,
        base_url: str,
        org: str,
        tenant: str,
    ):
        """Test list_files() with empty bucket."""
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets?$filter=Name eq 'empty-bucket'&$top=1",
            status_code=200,
            json={"value": [{"Id": 456, "Name": "empty-bucket", "Identifier": "id-2"}]},
        )

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/api/Buckets/456/ListFiles?takeHint=500",
            status_code=200,
            json={"items": [], "continuationToken": None},
        )

        files = list(service.list_files(name="empty-bucket"))
        assert len(files) == 0

    @pytest.mark.asyncio
    async def test_list_files_async(
        self,
        httpx_mock: HTTPXMock,
        service: BucketsService,
        base_url: str,
        org: str,
        tenant: str,
    ):
        """Test async version of list_files()."""
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets?$filter=Name eq 'test-bucket'&$top=1",
            status_code=200,
            json={"value": [{"Id": 123, "Name": "test-bucket", "Identifier": "id-1"}]},
        )

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/api/Buckets/123/ListFiles?takeHint=500",
            status_code=200,
            json={
                "items": [
                    {
                        "fullPath": "/async-file.txt",
                        "contentType": "text/plain",
                        "size": 100,
                        "lastModified": "2024-01-01T00:00:00Z",
                    }
                ],
                "continuationToken": None,
            },
        )

        files = [f async for f in service.list_files_async(name="test-bucket")]
        assert len(files) == 1
        assert files[0].path == "/async-file.txt"


class TestGetFiles:
    """Tests for get_files() method (OData GetFiles API)."""

    def test_get_files_basic(
        self,
        httpx_mock: HTTPXMock,
        service: BucketsService,
        base_url: str,
        org: str,
        tenant: str,
    ):
        """Test basic file listing with get_files()."""
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets?$filter=Name eq 'test-bucket'&$top=1",
            status_code=200,
            json={"value": [{"Id": 123, "Name": "test-bucket", "Identifier": "id-1"}]},
        )

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets(123)/UiPath.Server.Configuration.OData.GetFiles?directory=%2F&%24top=500",
            status_code=200,
            json={
                "value": [
                    {
                        "FullPath": "file1.txt",
                        "ContentType": "text/plain",
                        "Size": 100,
                        "IsDirectory": False,
                    },
                    {
                        "FullPath": "file2.txt",
                        "ContentType": "text/plain",
                        "Size": 200,
                        "IsDirectory": False,
                    },
                ]
            },
        )

        files = list(service.get_files(name="test-bucket"))
        assert len(files) == 2
        assert files[0].path == "file1.txt"
        assert files[0].size == 100
        assert files[1].path == "file2.txt"
        assert files[1].size == 200

    def test_get_files_with_glob(
        self,
        httpx_mock: HTTPXMock,
        service: BucketsService,
        base_url: str,
        org: str,
        tenant: str,
    ):
        """Test get_files() with glob pattern."""
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets?$filter=Name eq 'test-bucket'&$top=1",
            status_code=200,
            json={"value": [{"Id": 123, "Name": "test-bucket", "Identifier": "id-1"}]},
        )

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets(123)/UiPath.Server.Configuration.OData.GetFiles?directory=%2F&fileNameGlob=%2A.txt&%24top=500",
            status_code=200,
            json={
                "value": [
                    {
                        "FullPath": "file1.txt",
                        "ContentType": "text/plain",
                        "Size": 100,
                        "IsDirectory": False,
                    }
                ]
            },
        )

        files = list(service.get_files(name="test-bucket", file_name_glob="*.txt"))
        assert len(files) == 1
        assert files[0].path == "file1.txt"

    def test_get_files_with_recursive(
        self,
        httpx_mock: HTTPXMock,
        service: BucketsService,
        base_url: str,
        org: str,
        tenant: str,
    ):
        """Test get_files() with recursive flag."""
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets?$filter=Name eq 'test-bucket'&$top=1",
            status_code=200,
            json={"value": [{"Id": 123, "Name": "test-bucket", "Identifier": "id-1"}]},
        )

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets(123)/UiPath.Server.Configuration.OData.GetFiles?directory=docs&recursive=true&%24top=500",
            status_code=200,
            json={
                "value": [
                    {
                        "FullPath": "docs/file1.txt",
                        "ContentType": "text/plain",
                        "Size": 100,
                        "IsDirectory": False,
                    },
                    {
                        "FullPath": "docs/subdir/file2.txt",
                        "ContentType": "text/plain",
                        "Size": 200,
                        "IsDirectory": False,
                    },
                ]
            },
        )

        files = list(
            service.get_files(name="test-bucket", prefix="docs", recursive=True)
        )
        assert len(files) == 2
        assert files[1].path == "docs/subdir/file2.txt"

    def test_get_files_filters_directories(
        self,
        httpx_mock: HTTPXMock,
        service: BucketsService,
        base_url: str,
        org: str,
        tenant: str,
    ):
        """Test get_files() filters out directories."""
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets?$filter=Name eq 'test-bucket'&$top=1",
            status_code=200,
            json={"value": [{"Id": 123, "Name": "test-bucket", "Identifier": "id-1"}]},
        )

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets(123)/UiPath.Server.Configuration.OData.GetFiles?directory=%2F&%24top=500",
            status_code=200,
            json={
                "value": [
                    {
                        "FullPath": "file1.txt",
                        "ContentType": "text/plain",
                        "Size": 100,
                        "IsDirectory": False,
                    },
                    {
                        "FullPath": "folder1",
                        "ContentType": None,
                        "Size": 0,
                        "IsDirectory": True,
                    },
                    {
                        "FullPath": "file2.txt",
                        "ContentType": "text/plain",
                        "Size": 200,
                        "IsDirectory": False,
                    },
                ]
            },
        )

        files = list(service.get_files(name="test-bucket"))
        # Should only get 2 files, directory should be filtered out
        assert len(files) == 2
        assert all(not f.is_directory for f in files)

    def test_get_files_pagination(
        self,
        httpx_mock: HTTPXMock,
        service: BucketsService,
        base_url: str,
        org: str,
        tenant: str,
    ):
        """Test get_files() handles pagination with $skip and $top."""
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets?$filter=Name eq 'test-bucket'&$top=1",
            status_code=200,
            json={"value": [{"Id": 123, "Name": "test-bucket", "Identifier": "id-1"}]},
        )

        # First page (full page of 500)
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets(123)/UiPath.Server.Configuration.OData.GetFiles?directory=%2F&%24top=500",
            status_code=200,
            json={
                "value": [
                    {
                        "FullPath": f"file{i}.txt",
                        "ContentType": "text/plain",
                        "Size": 100,
                        "IsDirectory": False,
                    }
                    for i in range(500)
                ]
            },
        )

        # Second page (partial page of 50)
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets(123)/UiPath.Server.Configuration.OData.GetFiles?directory=%2F&%24skip=500&%24top=500",
            status_code=200,
            json={
                "value": [
                    {
                        "FullPath": f"file{i}.txt",
                        "ContentType": "text/plain",
                        "Size": 100,
                        "IsDirectory": False,
                    }
                    for i in range(500, 550)
                ]
            },
        )

        files = list(service.get_files(name="test-bucket"))
        assert len(files) == 550

    def test_get_files_empty(
        self,
        httpx_mock: HTTPXMock,
        service: BucketsService,
        base_url: str,
        org: str,
        tenant: str,
    ):
        """Test get_files() with empty bucket."""
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets?$filter=Name eq 'empty-bucket'&$top=1",
            status_code=200,
            json={"value": [{"Id": 456, "Name": "empty-bucket", "Identifier": "id-2"}]},
        )

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets(456)/UiPath.Server.Configuration.OData.GetFiles?directory=%2F&%24top=500",
            status_code=200,
            json={"value": []},
        )

        files = list(service.get_files(name="empty-bucket"))
        assert len(files) == 0

    def test_get_files_without_last_modified(
        self,
        httpx_mock: HTTPXMock,
        service: BucketsService,
        base_url: str,
        org: str,
        tenant: str,
    ):
        """Test get_files() handles missing lastModified field."""
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets?$filter=Name eq 'test-bucket'&$top=1",
            status_code=200,
            json={"value": [{"Id": 123, "Name": "test-bucket", "Identifier": "id-1"}]},
        )

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets(123)/UiPath.Server.Configuration.OData.GetFiles?directory=%2F&%24top=500",
            status_code=200,
            json={
                "value": [
                    {
                        "FullPath": "file1.txt",
                        "ContentType": "text/plain",
                        "Size": 100,
                        "IsDirectory": False,
                        # Note: No LastModified field (GetFiles doesn't provide it)
                    }
                ]
            },
        )

        files = list(service.get_files(name="test-bucket"))
        assert len(files) == 1
        assert files[0].last_modified is None  # Should be None, not error

    @pytest.mark.asyncio
    async def test_get_files_async(
        self,
        httpx_mock: HTTPXMock,
        service: BucketsService,
        base_url: str,
        org: str,
        tenant: str,
    ):
        """Test async version of get_files()."""
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets?$filter=Name eq 'test-bucket'&$top=1",
            status_code=200,
            json={"value": [{"Id": 123, "Name": "test-bucket", "Identifier": "id-1"}]},
        )

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets(123)/UiPath.Server.Configuration.OData.GetFiles?directory=%2F&%24top=500",
            status_code=200,
            json={
                "value": [
                    {
                        "FullPath": "async-file.txt",
                        "ContentType": "text/plain",
                        "Size": 100,
                        "IsDirectory": False,
                    }
                ]
            },
        )

        files = [f async for f in service.get_files_async(name="test-bucket")]
        assert len(files) == 1
        assert files[0].path == "async-file.txt"


class TestExistsFile:
    """Tests for exists_file() method."""

    def test_exists_file_found(
        self,
        httpx_mock: HTTPXMock,
        service: BucketsService,
        base_url: str,
        org: str,
        tenant: str,
    ):
        """Test exists_file() returns True when file is found."""
        # Mock bucket retrieve
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets?$filter=Name eq 'test-bucket'&$top=1",
            status_code=200,
            json={"value": [{"Id": 123, "Name": "test-bucket", "Identifier": "id-1"}]},
        )

        # Mock ListFiles response with matching file
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/api/Buckets/123/ListFiles?prefix=data%2Ffile.txt&takeHint=500",
            status_code=200,
            json={
                "items": [
                    {
                        "fullPath": "/data/file.txt",
                        "contentType": "text/plain",
                        "size": 100,
                        "lastModified": "2024-01-01T00:00:00Z",
                    }
                ],
                "continuationToken": None,
            },
        )

        result = service.exists_file(name="test-bucket", blob_file_path="data/file.txt")
        assert result is True

    def test_exists_file_not_found(
        self,
        httpx_mock: HTTPXMock,
        service: BucketsService,
        base_url: str,
        org: str,
        tenant: str,
    ):
        """Test exists_file() returns False when file is not found."""
        # Mock bucket retrieve
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets?$filter=Name eq 'test-bucket'&$top=1",
            status_code=200,
            json={"value": [{"Id": 123, "Name": "test-bucket", "Identifier": "id-1"}]},
        )

        # Mock ListFiles response with no matching files
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/api/Buckets/123/ListFiles?prefix=nonexistent.txt&takeHint=500",
            status_code=200,
            json={"items": [], "continuationToken": None},
        )

        result = service.exists_file(
            name="test-bucket", blob_file_path="nonexistent.txt"
        )
        assert result is False

    def test_exists_file_bucket_not_found(
        self,
        httpx_mock: HTTPXMock,
        service: BucketsService,
        base_url: str,
        org: str,
        tenant: str,
    ):
        """Test exists_file() raises LookupError when bucket doesn't exist."""
        # Mock bucket retrieve returning empty (bucket not found)
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets?$filter=Name eq 'nonexistent-bucket'&$top=1",
            status_code=200,
            json={"value": []},
        )

        # Should raise LookupError, not return False
        with pytest.raises(LookupError, match="Bucket.*not found"):
            service.exists_file(
                name="nonexistent-bucket", blob_file_path="some-file.txt"
            )

    def test_exists_file_short_circuit_on_match(
        self,
        httpx_mock: HTTPXMock,
        service: BucketsService,
        base_url: str,
        org: str,
        tenant: str,
    ):
        """Test exists_file() stops iteration on first match (short-circuit)."""
        # Mock bucket retrieve
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets?$filter=Name eq 'test-bucket'&$top=1",
            status_code=200,
            json={"value": [{"Id": 123, "Name": "test-bucket", "Identifier": "id-1"}]},
        )

        # Mock first page with matching file
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/api/Buckets/123/ListFiles?prefix=target.txt&takeHint=500",
            status_code=200,
            json={
                "items": [
                    {
                        "fullPath": "/target.txt",
                        "contentType": "text/plain",
                        "size": 100,
                        "lastModified": "2024-01-01T00:00:00Z",
                    }
                ],
                "continuationToken": "next-page-token",  # Has more pages
            },
        )

        # Should not request second page since file was found on first page
        result = service.exists_file(name="test-bucket", blob_file_path="target.txt")
        assert result is True

        # Verify only 2 requests were made (retrieve + first page)
        # NOT 3 requests (which would include second page)
        requests = httpx_mock.get_requests()
        assert len(requests) == 2

    def test_exists_file_searches_across_pages(
        self,
        httpx_mock: HTTPXMock,
        service: BucketsService,
        base_url: str,
        org: str,
        tenant: str,
    ):
        """Test exists_file() searches across multiple pages if needed."""
        # Mock bucket retrieve
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets?$filter=Name eq 'test-bucket'&$top=1",
            status_code=200,
            json={"value": [{"Id": 123, "Name": "test-bucket", "Identifier": "id-1"}]},
        )

        # First page - no match
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/api/Buckets/123/ListFiles?prefix=target.txt&takeHint=500",
            status_code=200,
            json={
                "items": [
                    {
                        "fullPath": "/other-file.txt",
                        "contentType": "text/plain",
                        "size": 100,
                        "lastModified": "2024-01-01T00:00:00Z",
                    }
                ],
                "continuationToken": "page2",
            },
        )

        # Second page - found
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/api/Buckets/123/ListFiles?prefix=target.txt&continuationToken=page2&takeHint=500",
            status_code=200,
            json={
                "items": [
                    {
                        "fullPath": "/target.txt",
                        "contentType": "text/plain",
                        "size": 200,
                        "lastModified": "2024-01-02T00:00:00Z",
                    }
                ],
                "continuationToken": None,
            },
        )

        result = service.exists_file(name="test-bucket", blob_file_path="target.txt")
        assert result is True

        # Should have made 3 requests (retrieve + page1 + page2)
        requests = httpx_mock.get_requests()
        assert len(requests) == 3

    def test_exists_file_with_folder_context(
        self,
        httpx_mock: HTTPXMock,
        service: BucketsService,
        base_url: str,
        org: str,
        tenant: str,
    ):
        """Test exists_file() with folder_path parameter."""
        # Mock bucket retrieve with folder path
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets?$filter=Name eq 'test-bucket'&$top=1",
            status_code=200,
            json={"value": [{"Id": 123, "Name": "test-bucket", "Identifier": "id-1"}]},
        )

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/api/Buckets/123/ListFiles?prefix=file.txt&takeHint=500",
            status_code=200,
            json={
                "items": [
                    {
                        "fullPath": "/file.txt",
                        "contentType": "text/plain",
                        "size": 100,
                        "lastModified": "2024-01-01T00:00:00Z",
                    }
                ],
                "continuationToken": None,
            },
        )

        result = service.exists_file(
            name="test-bucket", blob_file_path="file.txt", folder_path="Production"
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_exists_file_async(
        self,
        httpx_mock: HTTPXMock,
        service: BucketsService,
        base_url: str,
        org: str,
        tenant: str,
    ):
        """Test async version of exists_file()."""
        # Mock bucket retrieve
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets?$filter=Name eq 'test-bucket'&$top=1",
            status_code=200,
            json={"value": [{"Id": 123, "Name": "test-bucket", "Identifier": "id-1"}]},
        )

        # Mock ListFiles response
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/api/Buckets/123/ListFiles?prefix=async-file.txt&takeHint=500",
            status_code=200,
            json={
                "items": [
                    {
                        "fullPath": "/async-file.txt",
                        "contentType": "text/plain",
                        "size": 100,
                        "lastModified": "2024-01-01T00:00:00Z",
                    }
                ],
                "continuationToken": None,
            },
        )

        result = await service.exists_file_async(
            name="test-bucket", blob_file_path="async-file.txt"
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_exists_file_async_not_found(
        self,
        httpx_mock: HTTPXMock,
        service: BucketsService,
        base_url: str,
        org: str,
        tenant: str,
    ):
        """Test async version returns False when file not found."""
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets?$filter=Name eq 'test-bucket'&$top=1",
            status_code=200,
            json={"value": [{"Id": 123, "Name": "test-bucket", "Identifier": "id-1"}]},
        )

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/api/Buckets/123/ListFiles?prefix=missing.txt&takeHint=500",
            status_code=200,
            json={"items": [], "continuationToken": None},
        )

        result = await service.exists_file_async(
            name="test-bucket", blob_file_path="missing.txt"
        )
        assert result is False

    def test_exists_file_empty_path_raises_error(self, service: BucketsService):
        """Test exists_file() raises ValueError for empty blob_file_path."""
        with pytest.raises(ValueError, match="blob_file_path cannot be empty"):
            service.exists_file(name="test-bucket", blob_file_path="")

    def test_exists_file_whitespace_path_raises_error(self, service: BucketsService):
        """Test exists_file() raises ValueError for whitespace-only blob_file_path."""
        with pytest.raises(ValueError, match="blob_file_path cannot be empty"):
            service.exists_file(name="test-bucket", blob_file_path="   ")

    @pytest.mark.asyncio
    async def test_exists_file_async_empty_path_raises_error(
        self, service: BucketsService
    ):
        """Test async version raises ValueError for empty blob_file_path."""
        with pytest.raises(ValueError, match="blob_file_path cannot be empty"):
            await service.exists_file_async(name="test-bucket", blob_file_path="")

    @pytest.mark.asyncio
    async def test_exists_file_async_whitespace_path_raises_error(
        self, service: BucketsService
    ):
        """Test async version raises ValueError for whitespace-only blob_file_path."""
        with pytest.raises(ValueError, match="blob_file_path cannot be empty"):
            await service.exists_file_async(name="test-bucket", blob_file_path="  ")
