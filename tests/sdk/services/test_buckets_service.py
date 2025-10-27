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

    class TestGetFiles:
        def test_get_files_by_key(
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
                url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets(123)/UiPath.Server.Configuration.OData.GetFiles",
                status_code=200,
                json={
                    "value": [
                        {"FullPath": "file1.txt", "IsDirectory": False},
                        {"FullPath": "file2.pdf", "IsDirectory": False},
                        {"FullPath": "subfolder/", "IsDirectory": True},
                        {"FullPath": "subfolder/file3.doc", "IsDirectory": False},
                    ]
                },
            )

            files = service.get_files(key=bucket_key)
            assert len(files) == 3
            assert "file1.txt" in files
            assert "file2.pdf" in files
            assert "subfolder/file3.doc" in files
            assert "subfolder/" not in files

        def test_get_files_by_name(
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

            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets(123)/UiPath.Server.Configuration.OData.GetFiles",
                status_code=200,
                json={
                    "value": [
                        {"FullPath": "file1.txt", "IsDirectory": False},
                        {"FullPath": "file2.pdf", "IsDirectory": False},
                    ]
                },
            )

            files = service.get_files(name=bucket_name)
            assert len(files) == 2
            assert "file1.txt" in files
            assert "file2.pdf" in files

        def test_get_files_with_prefix(
            self,
            httpx_mock: HTTPXMock,
            service: BucketsService,
            base_url: str,
            org: str,
            tenant: str,
        ):
            bucket_key = "bucket-key"
            prefix = "documents/"
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
                url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets(123)/UiPath.Server.Configuration.OData.GetFiles?directory={prefix}",
                status_code=200,
                json={
                    "value": [
                        {"FullPath": "documents/report.pdf", "IsDirectory": False},
                        {"FullPath": "documents/invoice.pdf", "IsDirectory": False},
                        {"FullPath": "documents/archive/", "IsDirectory": True},
                    ]
                },
            )

            files = service.get_files(key=bucket_key, prefix=prefix)
            assert len(files) == 2
            assert "documents/report.pdf" in files
            assert "documents/invoice.pdf" in files
            assert "documents/archive/" not in files

        def test_get_files_empty_bucket(
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
                url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets(123)/UiPath.Server.Configuration.OData.GetFiles",
                status_code=200,
                json={"value": []},
            )

            files = service.get_files(key=bucket_key)
            assert len(files) == 0
            assert files == []

        @pytest.mark.asyncio
        async def test_get_files_by_key_async(
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
                url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets(123)/UiPath.Server.Configuration.OData.GetFiles",
                status_code=200,
                json={
                    "value": [
                        {"FullPath": "file1.txt", "IsDirectory": False},
                        {"FullPath": "file2.pdf", "IsDirectory": False},
                        {"FullPath": "subfolder/", "IsDirectory": True},
                        {"FullPath": "subfolder/file3.doc", "IsDirectory": False},
                    ]
                },
            )

            files = await service.get_files_async(key=bucket_key)
            assert len(files) == 3
            assert "file1.txt" in files
            assert "file2.pdf" in files
            assert "subfolder/file3.doc" in files
            assert "subfolder/" not in files

        @pytest.mark.asyncio
        async def test_get_files_by_name_async(
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

            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets(123)/UiPath.Server.Configuration.OData.GetFiles",
                status_code=200,
                json={
                    "value": [
                        {"FullPath": "file1.txt", "IsDirectory": False},
                        {"FullPath": "file2.pdf", "IsDirectory": False},
                    ]
                },
            )

            files = await service.get_files_async(name=bucket_name)
            assert len(files) == 2
            assert "file1.txt" in files
            assert "file2.pdf" in files

        @pytest.mark.asyncio
        async def test_get_files_with_prefix_async(
            self,
            httpx_mock: HTTPXMock,
            service: BucketsService,
            base_url: str,
            org: str,
            tenant: str,
        ):
            bucket_key = "bucket-key"
            prefix = "documents/"
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
                url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets(123)/UiPath.Server.Configuration.OData.GetFiles?directory={prefix}",
                status_code=200,
                json={
                    "value": [
                        {"FullPath": "documents/report.pdf", "IsDirectory": False},
                        {"FullPath": "documents/invoice.pdf", "IsDirectory": False},
                        {"FullPath": "documents/archive/", "IsDirectory": True},
                    ]
                },
            )

            files = await service.get_files_async(key=bucket_key, prefix=prefix)
            assert len(files) == 2
            assert "documents/report.pdf" in files
            assert "documents/invoice.pdf" in files
            assert "documents/archive/" not in files

        @pytest.mark.asyncio
        async def test_get_files_empty_bucket_async(
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
                url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets(123)/UiPath.Server.Configuration.OData.GetFiles",
                status_code=200,
                json={"value": []},
            )

            files = await service.get_files_async(key=bucket_key)
            assert len(files) == 0
            assert files == []

    class TestListFiles:
        def test_list_files_by_key(
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
                url=f"{base_url}{org}{tenant}/orchestrator_/api/Buckets/123/ListFiles",
                status_code=200,
                json={
                    "items": [
                        {"fullPath": "file1.txt", "size": 1024},
                        {"fullPath": "file2.pdf", "size": 2048},
                        {"fullPath": "subfolder/file3.doc", "size": 512},
                    ],
                    "continuationToken": None,
                },
            )

            result = service.list_files(key=bucket_key)
            assert isinstance(result, dict)
            assert "files" in result
            assert "continuation_token" in result
            assert len(result["files"]) == 3
            assert "file1.txt" in result["files"]
            assert "file2.pdf" in result["files"]
            assert "subfolder/file3.doc" in result["files"]
            assert result["continuation_token"] is None

        def test_list_files_by_name(
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

            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/orchestrator_/api/Buckets/123/ListFiles",
                status_code=200,
                json={
                    "items": [
                        {"fullPath": "file1.txt"},
                        {"fullPath": "file2.pdf"},
                    ],
                    "continuationToken": None,
                },
            )

            result = service.list_files(name=bucket_name)
            assert len(result["files"]) == 2
            assert "file1.txt" in result["files"]
            assert "file2.pdf" in result["files"]

        def test_list_files_with_prefix(
            self,
            httpx_mock: HTTPXMock,
            service: BucketsService,
            base_url: str,
            org: str,
            tenant: str,
        ):
            bucket_key = "bucket-key"
            prefix = "documents/"
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
                url=f"{base_url}{org}{tenant}/orchestrator_/api/Buckets/123/ListFiles?prefix={prefix}",
                status_code=200,
                json={
                    "items": [
                        {"fullPath": "documents/report.pdf"},
                        {"fullPath": "documents/invoice.pdf"},
                    ],
                    "continuationToken": None,
                },
            )

            result = service.list_files(key=bucket_key, prefix=prefix)
            assert len(result["files"]) == 2
            assert "documents/report.pdf" in result["files"]
            assert "documents/invoice.pdf" in result["files"]

        def test_list_files_with_continuation_token(
            self,
            httpx_mock: HTTPXMock,
            service: BucketsService,
            base_url: str,
            org: str,
            tenant: str,
        ):
            bucket_key = "bucket-key"
            continuation_token = "token-123"
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
                url=f"{base_url}{org}{tenant}/orchestrator_/api/Buckets/123/ListFiles?continuationToken={continuation_token}",
                status_code=200,
                json={
                    "items": [
                        {"fullPath": "file10.txt"},
                        {"fullPath": "file11.pdf"},
                    ],
                    "continuationToken": "token-456",
                },
            )

            result = service.list_files(key=bucket_key, continuation_token=continuation_token)
            assert len(result["files"]) == 2
            assert "file10.txt" in result["files"]
            assert "file11.pdf" in result["files"]
            assert result["continuation_token"] == "token-456"

        def test_list_files_with_take_hint(
            self,
            httpx_mock: HTTPXMock,
            service: BucketsService,
            base_url: str,
            org: str,
            tenant: str,
        ):
            bucket_key = "bucket-key"
            take_hint = 100
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
                url=f"{base_url}{org}{tenant}/orchestrator_/api/Buckets/123/ListFiles?takeHint={take_hint}",
                status_code=200,
                json={
                    "items": [{"fullPath": f"file{i}.txt"} for i in range(100)],
                    "continuationToken": "next-token",
                },
            )

            result = service.list_files(key=bucket_key, take_hint=take_hint)
            assert len(result["files"]) == 100
            assert result["continuation_token"] == "next-token"

        def test_list_files_empty_bucket(
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
                url=f"{base_url}{org}{tenant}/orchestrator_/api/Buckets/123/ListFiles",
                status_code=200,
                json={"items": [], "continuationToken": None},
            )

            result = service.list_files(key=bucket_key)
            assert len(result["files"]) == 0
            assert result["files"] == []
            assert result["continuation_token"] is None

        @pytest.mark.asyncio
        async def test_list_files_by_key_async(
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
                url=f"{base_url}{org}{tenant}/orchestrator_/api/Buckets/123/ListFiles",
                status_code=200,
                json={
                    "items": [
                        {"fullPath": "file1.txt", "size": 1024},
                        {"fullPath": "file2.pdf", "size": 2048},
                        {"fullPath": "subfolder/file3.doc", "size": 512},
                    ],
                    "continuationToken": None,
                },
            )

            result = await service.list_files_async(key=bucket_key)
            assert isinstance(result, dict)
            assert "files" in result
            assert "continuation_token" in result
            assert len(result["files"]) == 3
            assert "file1.txt" in result["files"]
            assert "file2.pdf" in result["files"]
            assert "subfolder/file3.doc" in result["files"]
            assert result["continuation_token"] is None

        @pytest.mark.asyncio
        async def test_list_files_by_name_async(
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

            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/orchestrator_/api/Buckets/123/ListFiles",
                status_code=200,
                json={
                    "items": [
                        {"fullPath": "file1.txt"},
                        {"fullPath": "file2.pdf"},
                    ],
                    "continuationToken": None,
                },
            )

            result = await service.list_files_async(name=bucket_name)
            assert len(result["files"]) == 2
            assert "file1.txt" in result["files"]
            assert "file2.pdf" in result["files"]

        @pytest.mark.asyncio
        async def test_list_files_with_prefix_async(
            self,
            httpx_mock: HTTPXMock,
            service: BucketsService,
            base_url: str,
            org: str,
            tenant: str,
        ):
            bucket_key = "bucket-key"
            prefix = "documents/"
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
                url=f"{base_url}{org}{tenant}/orchestrator_/api/Buckets/123/ListFiles?prefix={prefix}",
                status_code=200,
                json={
                    "items": [
                        {"fullPath": "documents/report.pdf"},
                        {"fullPath": "documents/invoice.pdf"},
                    ],
                    "continuationToken": None,
                },
            )

            result = await service.list_files_async(key=bucket_key, prefix=prefix)
            assert len(result["files"]) == 2
            assert "documents/report.pdf" in result["files"]
            assert "documents/invoice.pdf" in result["files"]

        @pytest.mark.asyncio
        async def test_list_files_with_continuation_token_async(
            self,
            httpx_mock: HTTPXMock,
            service: BucketsService,
            base_url: str,
            org: str,
            tenant: str,
        ):
            bucket_key = "bucket-key"
            continuation_token = "token-123"
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
                url=f"{base_url}{org}{tenant}/orchestrator_/api/Buckets/123/ListFiles?continuationToken={continuation_token}",
                status_code=200,
                json={
                    "items": [
                        {"fullPath": "file10.txt"},
                        {"fullPath": "file11.pdf"},
                    ],
                    "continuationToken": "token-456",
                },
            )

            result = await service.list_files_async(
                key=bucket_key, continuation_token=continuation_token
            )
            assert len(result["files"]) == 2
            assert "file10.txt" in result["files"]
            assert "file11.pdf" in result["files"]
            assert result["continuation_token"] == "token-456"

        @pytest.mark.asyncio
        async def test_list_files_empty_bucket_async(
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
                url=f"{base_url}{org}{tenant}/orchestrator_/api/Buckets/123/ListFiles",
                status_code=200,
                json={"items": [], "continuationToken": None},
            )

            result = await service.list_files_async(key=bucket_key)
            assert len(result["files"]) == 0
            assert result["files"] == []
            assert result["continuation_token"] is None
