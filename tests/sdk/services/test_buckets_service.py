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
                url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets/UiPath.Server.Configuration.OData.GetByKey(identifier={bucket_key})",
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
                url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets/UiPath.Server.Configuration.OData.GetByKey(identifier={bucket_key})",
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
                url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets/UiPath.Server.Configuration.OData.GetByKey(identifier={bucket_key})",
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
                url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets/UiPath.Server.Configuration.OData.GetByKey(identifier={bucket_key})",
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
                url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets/UiPath.Server.Configuration.OData.GetByKey(identifier={bucket_key})",
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
