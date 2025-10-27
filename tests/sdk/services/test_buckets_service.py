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
