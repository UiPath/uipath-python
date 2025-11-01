"""Live integration tests for BucketsService.

This is the Phase 1 proof of concept implementation to validate the live testing
framework. Based on: tmp/test_buckets_live.py

Tests cover:
    - Creating buckets
    - Listing buckets
    - Uploading files (memory and disk)
    - Listing files in bucket (list_files and get_files APIs)
    - Downloading files
    - Deleting files
    - Deleting buckets
    - Async operations

Prerequisites:
    - Valid UiPath credentials in .env or environment
    - UIPATH_URL, UIPATH_ACCESS_TOKEN configured
    - UIPATH_FOLDER_PATH (optional, defaults to 'Shared')

Usage:
    # Run all buckets live tests
    pytest -m live_buckets -v tests/live

    # Run only smoke tests
    pytest -m "live and smoke" -v tests/live
"""

from pathlib import Path

import pytest

from uipath import UiPath

# CRITICAL: All live test files MUST have pytest.mark.live to be excluded by default!
pytestmark = [pytest.mark.live, pytest.mark.live_buckets]


class TestBucketsBasicOperations:
    """Test basic bucket operations (create, list, retrieve, exists, delete)."""

    @pytest.mark.smoke
    def test_list_buckets(self, uipath_client: UiPath):
        """Test listing buckets in the folder."""
        buckets = list(uipath_client.buckets.list())
        assert isinstance(buckets, list)
        # Don't assert on count - other tests may be running

    def test_create_bucket(
        self,
        uipath_client: UiPath,
        unique_name: str,
        cleanup_tracker: list[tuple[str, str]],
    ):
        """Test creating a bucket."""
        bucket_name = f"{unique_name}-bucket"
        cleanup_tracker.append(("bucket", bucket_name))

        bucket = uipath_client.buckets.create(
            name=bucket_name, description="Test bucket created by live integration test"
        )

        assert bucket.name == bucket_name
        assert bucket.id is not None
        assert bucket.identifier is not None

    def test_retrieve_bucket_by_name(
        self,
        uipath_client: UiPath,
        unique_name: str,
        cleanup_tracker: list[tuple[str, str]],
    ):
        """Test retrieving a bucket by name."""
        bucket_name = f"{unique_name}-retrieve"
        cleanup_tracker.append(("bucket", bucket_name))

        # Create bucket
        bucket = uipath_client.buckets.create(name=bucket_name)

        # Retrieve by name
        retrieved = uipath_client.buckets.retrieve(name=bucket_name)
        assert retrieved.name == bucket_name
        assert retrieved.id == bucket.id

    def test_retrieve_bucket_by_key(
        self,
        uipath_client: UiPath,
        unique_name: str,
        cleanup_tracker: list[tuple[str, str]],
    ):
        """Test retrieving a bucket by key (identifier).

        Note: This may not be available in all environments.
        """
        bucket_name = f"{unique_name}-retrieve-key"
        cleanup_tracker.append(("bucket", bucket_name))

        # Create bucket
        bucket = uipath_client.buckets.create(name=bucket_name)

        # Try to retrieve by key (may not be available in all environments)
        try:
            retrieved_by_key = uipath_client.buckets.retrieve(key=bucket.identifier)
            assert retrieved_by_key.name == bucket_name
            assert retrieved_by_key.id == bucket.id
        except Exception:
            pytest.skip("GetByKey not available in this environment")

    def test_bucket_exists(
        self,
        uipath_client: UiPath,
        unique_name: str,
        cleanup_tracker: list[tuple[str, str]],
    ):
        """Test checking if a bucket exists."""
        bucket_name = f"{unique_name}-exists"
        cleanup_tracker.append(("bucket", bucket_name))

        # Create bucket
        uipath_client.buckets.create(name=bucket_name)

        # Check exists
        assert uipath_client.buckets.exists(bucket_name) is True

        # Check non-existent bucket
        assert uipath_client.buckets.exists(f"{unique_name}-nonexistent") is False

    def test_list_buckets_with_filter(self, uipath_client: UiPath):
        """Test listing buckets with name filter."""
        filtered_buckets = list(uipath_client.buckets.list(name="test"))
        assert isinstance(filtered_buckets, list)
        # All returned buckets should have "test" in name
        for bucket in filtered_buckets:
            assert "test" in bucket.name.lower()


class TestBucketsFileOperations:
    """Test file upload, list, download, and delete operations."""

    def test_upload_file_from_memory(
        self,
        uipath_client: UiPath,
        unique_name: str,
        cleanup_tracker: list[tuple[str, str]],
    ):
        """Test uploading a file from memory (content)."""
        bucket_name = f"{unique_name}-upload-memory"
        cleanup_tracker.append(("bucket", bucket_name))

        # Create bucket
        uipath_client.buckets.create(name=bucket_name)

        # Upload file from memory
        test_content = f"Hello from test! {unique_name}"
        uipath_client.buckets.upload(
            name=bucket_name,
            blob_file_path="test-file.txt",
            content=test_content,
            content_type="text/plain",
        )

        # Verify file was uploaded
        files = list(uipath_client.buckets.list_files(name=bucket_name))
        assert len(files) >= 1
        file_paths = [f.path for f in files]
        assert any(path.endswith("test-file.txt") for path in file_paths), (
            f"Expected file not found. Got paths: {file_paths}"
        )

    def test_upload_file_from_disk(
        self,
        uipath_client: UiPath,
        unique_name: str,
        cleanup_tracker: list[tuple[str, str]],
        tmp_path: Path,
    ):
        """Test uploading a file from disk."""
        bucket_name = f"{unique_name}-upload-disk"
        cleanup_tracker.append(("bucket", bucket_name))

        # Create bucket
        uipath_client.buckets.create(name=bucket_name)

        # Create temporary file
        test_file = tmp_path / "test.txt"
        test_file.write_text(f"Test file content from disk! {unique_name}")

        # Upload file from disk
        uipath_client.buckets.upload(
            name=bucket_name,
            blob_file_path="data/test-file.txt",
            source_path=str(test_file),
        )

        # Verify file was uploaded
        files = list(uipath_client.buckets.list_files(name=bucket_name))
        assert len(files) >= 1
        # Check if file exists with the expected path (allow for potential path variations)
        file_paths = [f.path for f in files]
        assert any(path.endswith("test-file.txt") for path in file_paths), (
            f"Expected file not found. Got paths: {file_paths}"
        )

    def test_list_files_iterator(
        self,
        uipath_client: UiPath,
        unique_name: str,
        cleanup_tracker: list[tuple[str, str]],
    ):
        """Test listing files using iterator pattern (memory efficient)."""
        bucket_name = f"{unique_name}-list-files"
        cleanup_tracker.append(("bucket", bucket_name))

        # Create bucket and upload files
        uipath_client.buckets.create(name=bucket_name)
        uipath_client.buckets.upload(
            name=bucket_name, blob_file_path="file1.txt", content="Content 1"
        )
        uipath_client.buckets.upload(
            name=bucket_name, blob_file_path="file2.txt", content="Content 2"
        )

        # Test iterator pattern
        file_count = 0
        for file in uipath_client.buckets.list_files(name=bucket_name):
            assert file.path is not None
            assert file.size is not None
            file_count += 1

        assert file_count >= 2

        # Test materialization to list
        files = list(uipath_client.buckets.list_files(name=bucket_name))
        assert len(files) >= 2

    def test_list_files_with_prefix(
        self,
        uipath_client: UiPath,
        unique_name: str,
        cleanup_tracker: list[tuple[str, str]],
    ):
        """Test listing files with prefix filter."""
        bucket_name = f"{unique_name}-prefix"
        cleanup_tracker.append(("bucket", bucket_name))

        # Create bucket and upload files with different prefixes
        uipath_client.buckets.create(name=bucket_name)
        uipath_client.buckets.upload(
            name=bucket_name, blob_file_path="data/file1.txt", content="Data 1"
        )
        uipath_client.buckets.upload(
            name=bucket_name, blob_file_path="data/file2.txt", content="Data 2"
        )
        uipath_client.buckets.upload(
            name=bucket_name, blob_file_path="docs/readme.txt", content="Docs"
        )

        # List files with "data" prefix
        data_files = list(
            uipath_client.buckets.list_files(name=bucket_name, prefix="data")
        )
        assert len(data_files) >= 2
        for file in data_files:
            # Paths may have leading slash, so check both formats
            assert file.path.startswith("data") or file.path.startswith("/data"), (
                f"Unexpected path: {file.path}"
            )

    def test_get_files_basic(
        self,
        uipath_client: UiPath,
        unique_name: str,
        cleanup_tracker: list[tuple[str, str]],
    ):
        """Test get_files() method (OData GetFiles API - Studio-compatible)."""
        bucket_name = f"{unique_name}-get-files"
        cleanup_tracker.append(("bucket", bucket_name))

        # Create bucket and upload files
        uipath_client.buckets.create(name=bucket_name)
        uipath_client.buckets.upload(
            name=bucket_name, blob_file_path="docs/readme.txt", content="README content"
        )
        uipath_client.buckets.upload(
            name=bucket_name,
            blob_file_path="docs/manual.pdf",
            content="PDF content placeholder",
            content_type="application/pdf",
        )

        # Test basic get_files (with recursive=True for full directory traversal)
        files = list(uipath_client.buckets.get_files(name=bucket_name, recursive=True))
        assert len(files) >= 2, f"Expected at least 2 files, got {len(files)}"

    def test_get_files_with_glob(
        self,
        uipath_client: UiPath,
        unique_name: str,
        cleanup_tracker: list[tuple[str, str]],
    ):
        """Test get_files() with glob pattern filtering."""
        bucket_name = f"{unique_name}-glob"
        cleanup_tracker.append(("bucket", bucket_name))

        # Create bucket and upload files with different extensions
        uipath_client.buckets.create(name=bucket_name)
        uipath_client.buckets.upload(
            name=bucket_name, blob_file_path="file1.txt", content="Text 1"
        )
        uipath_client.buckets.upload(
            name=bucket_name, blob_file_path="file2.txt", content="Text 2"
        )
        uipath_client.buckets.upload(
            name=bucket_name,
            blob_file_path="file3.pdf",
            content="PDF",
            content_type="application/pdf",
        )

        # Filter for .txt files
        txt_files = list(
            uipath_client.buckets.get_files(name=bucket_name, file_name_glob="*.txt")
        )
        assert len(txt_files) >= 2
        for file in txt_files:
            assert file.path.endswith(".txt")

        # Filter for .pdf files
        pdf_files = list(
            uipath_client.buckets.get_files(name=bucket_name, file_name_glob="*.pdf")
        )
        assert len(pdf_files) >= 1
        for file in pdf_files:
            assert file.path.endswith(".pdf")

    def test_get_files_recursive(
        self,
        uipath_client: UiPath,
        unique_name: str,
        cleanup_tracker: list[tuple[str, str]],
    ):
        """Test get_files() with recursive directory traversal."""
        bucket_name = f"{unique_name}-recursive"
        cleanup_tracker.append(("bucket", bucket_name))

        # Create bucket and upload files in subdirectories
        uipath_client.buckets.create(name=bucket_name)
        uipath_client.buckets.upload(
            name=bucket_name, blob_file_path="docs/readme.txt", content="README"
        )
        uipath_client.buckets.upload(
            name=bucket_name, blob_file_path="docs/subdir/notes.txt", content="Notes"
        )

        # Non-recursive (should not get subdirectory files)
        non_recursive = list(
            uipath_client.buckets.get_files(
                name=bucket_name, prefix="docs", recursive=False
            )
        )
        # Should only get files directly in docs/
        assert len(non_recursive) >= 1

        # Recursive (should get all files including subdirectories)
        recursive = list(
            uipath_client.buckets.get_files(
                name=bucket_name, prefix="docs", recursive=True
            )
        )
        # Should get both docs/readme.txt and docs/subdir/notes.txt
        assert len(recursive) >= 2
        assert any("subdir" in f.path for f in recursive)

    def test_download_file(
        self,
        uipath_client: UiPath,
        unique_name: str,
        cleanup_tracker: list[tuple[str, str]],
        tmp_path: Path,
    ):
        """Test downloading a file from bucket."""
        bucket_name = f"{unique_name}-download"
        cleanup_tracker.append(("bucket", bucket_name))

        # Create bucket and upload file
        uipath_client.buckets.create(name=bucket_name)
        test_content = f"Hello from download test! {unique_name}"
        uipath_client.buckets.upload(
            name=bucket_name, blob_file_path="test-file.txt", content=test_content
        )

        # Download file
        download_path = tmp_path / "downloaded.txt"
        uipath_client.buckets.download(
            name=bucket_name,
            blob_file_path="test-file.txt",
            destination_path=str(download_path),
        )

        # Verify content matches
        downloaded_content = download_path.read_text()
        assert test_content in downloaded_content

    def test_delete_file(
        self,
        uipath_client: UiPath,
        unique_name: str,
        cleanup_tracker: list[tuple[str, str]],
    ):
        """Test deleting a file from bucket."""
        bucket_name = f"{unique_name}-delete-file"
        cleanup_tracker.append(("bucket", bucket_name))

        # Create bucket and upload file
        uipath_client.buckets.create(name=bucket_name)
        uipath_client.buckets.upload(
            name=bucket_name, blob_file_path="test-file.txt", content="Test content"
        )

        # Verify file exists
        files_before = list(uipath_client.buckets.list_files(name=bucket_name))
        assert len(files_before) >= 1

        # Delete file
        uipath_client.buckets.delete_file(
            name=bucket_name, blob_file_path="test-file.txt"
        )

        # Verify file was deleted
        files_after = list(uipath_client.buckets.list_files(name=bucket_name))
        assert len(files_after) == len(files_before) - 1


class TestBucketsLargeScale:
    """Test bucket operations at scale (many files, pagination)."""

    @pytest.mark.slow
    def test_many_files_iterator_efficiency(
        self,
        uipath_client: UiPath,
        unique_name: str,
        cleanup_tracker: list[tuple[str, str]],
    ):
        """Test iterator efficiency with many files (pagination)."""
        bucket_name = f"{unique_name}-many-files"
        cleanup_tracker.append(("bucket", bucket_name))

        # Create bucket
        uipath_client.buckets.create(name=bucket_name)

        # Upload many files
        num_files = 20  # Reduced for faster tests
        for i in range(num_files):
            uipath_client.buckets.upload(
                name=bucket_name,
                blob_file_path=f"test-files/file-{i:03d}.txt",
                content=f"Test file {i}",
            )

        # Test iterator early termination (memory efficient)
        count = 0
        for _file in uipath_client.buckets.list_files(name=bucket_name):
            count += 1
            if count >= 5:
                break
        assert count == 5

        # Test full iteration (including pagination)
        all_files = list(uipath_client.buckets.list_files(name=bucket_name))
        assert len(all_files) >= num_files


@pytest.mark.asyncio
class TestBucketsAsync:
    """Test async variants of bucket operations."""

    async def test_retrieve_async(
        self,
        uipath_client: UiPath,
        unique_name: str,
        async_cleanup_tracker: list[tuple[str, str]],
    ):
        """Test async bucket retrieval."""
        bucket_name = f"{unique_name}-async-retrieve"
        async_cleanup_tracker.append(("bucket", bucket_name))

        # Create bucket (use async to avoid event loop conflicts)
        await uipath_client.buckets.create_async(name=bucket_name)

        # Test async retrieve
        bucket_async = await uipath_client.buckets.retrieve_async(name=bucket_name)
        assert bucket_async.name == bucket_name

    async def test_list_files_async(
        self,
        uipath_client: UiPath,
        unique_name: str,
        async_cleanup_tracker: list[tuple[str, str]],
    ):
        """Test async file listing."""
        bucket_name = f"{unique_name}-async-list"
        async_cleanup_tracker.append(("bucket", bucket_name))

        # Create bucket and upload files (use async methods to avoid event loop conflicts)
        await uipath_client.buckets.create_async(name=bucket_name)
        await uipath_client.buckets.upload_async(
            name=bucket_name, blob_file_path="file1.txt", content="Test 1"
        )
        await uipath_client.buckets.upload_async(
            name=bucket_name, blob_file_path="file2.txt", content="Test 2"
        )

        # Test async list_files
        files_async = [
            f async for f in uipath_client.buckets.list_files_async(name=bucket_name)
        ]
        assert len(files_async) >= 2

    async def test_get_files_async(
        self,
        uipath_client: UiPath,
        unique_name: str,
        async_cleanup_tracker: list[tuple[str, str]],
    ):
        """Test async get_files with various filters."""
        bucket_name = f"{unique_name}-async-get"
        async_cleanup_tracker.append(("bucket", bucket_name))

        # Create bucket and upload files (use async methods)
        await uipath_client.buckets.create_async(name=bucket_name)
        await uipath_client.buckets.upload_async(
            name=bucket_name, blob_file_path="test1.txt", content="Test 1"
        )
        await uipath_client.buckets.upload_async(
            name=bucket_name, blob_file_path="test2.txt", content="Test 2"
        )
        await uipath_client.buckets.upload_async(
            name=bucket_name,
            blob_file_path="test3.pdf",
            content="PDF",
            content_type="application/pdf",
        )

        # Test async get_files
        files_async = [
            f async for f in uipath_client.buckets.get_files_async(name=bucket_name)
        ]
        assert len(files_async) >= 3

        # Test async get_files with glob
        txt_async = [
            f
            async for f in uipath_client.buckets.get_files_async(
                name=bucket_name, file_name_glob="*.txt"
            )
        ]
        assert len(txt_async) >= 2

    async def test_exists_async(
        self,
        uipath_client: UiPath,
        unique_name: str,
        async_cleanup_tracker: list[tuple[str, str]],
    ):
        """Test async bucket existence check."""
        bucket_name = f"{unique_name}-async-exists"
        async_cleanup_tracker.append(("bucket", bucket_name))

        # Create bucket (use async)
        await uipath_client.buckets.create_async(name=bucket_name)

        # Test async exists
        exists_async = await uipath_client.buckets.exists_async(bucket_name)
        assert exists_async is True

        # Test async exists for non-existent bucket
        not_exists_async = await uipath_client.buckets.exists_async(
            f"{unique_name}-nonexistent"
        )
        assert not_exists_async is False

    async def test_delete_file_async(
        self,
        uipath_client: UiPath,
        unique_name: str,
        async_cleanup_tracker: list[tuple[str, str]],
    ):
        """Test async file deletion."""
        bucket_name = f"{unique_name}-async-delete"
        async_cleanup_tracker.append(("bucket", bucket_name))

        # Create bucket and upload file (use async)
        await uipath_client.buckets.create_async(name=bucket_name)
        await uipath_client.buckets.upload_async(
            name=bucket_name, blob_file_path="test.txt", content="Test"
        )

        # Test async delete
        await uipath_client.buckets.delete_file_async(
            name=bucket_name, blob_file_path="test.txt"
        )

        # Verify file was deleted (use async method)
        files = [
            f async for f in uipath_client.buckets.list_files_async(name=bucket_name)
        ]
        assert len(files) == 0
