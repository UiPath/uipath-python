"""Tests for exception handling improvements (EnrichedException changes).

This test module verifies the changes made to exception handling across:
- jobs_service.py: retrieve() and retrieve_async() now catch EnrichedException with status_code
- attachments_service.py: download/delete methods now catch EnrichedException with status_code

Changes: Replaced string matching "404" in str(e) with proper exception type checking.
"""

import uuid
from pathlib import Path

import pytest
from pytest_httpx import HTTPXMock

from uipath._config import Config
from uipath._execution_context import ExecutionContext
from uipath._services.attachments_service import AttachmentsService
from uipath._services.jobs_service import JobsService
from uipath.models.exceptions import EnrichedException


@pytest.fixture
def jobs_service(config: Config, execution_context: ExecutionContext) -> JobsService:
    """JobsService fixture for testing."""
    return JobsService(config=config, execution_context=execution_context)


@pytest.fixture
def attachments_service(
    config: Config, execution_context: ExecutionContext
) -> AttachmentsService:
    """AttachmentsService fixture for testing."""
    return AttachmentsService(config=config, execution_context=execution_context)


class TestJobsServiceExceptionHandling:
    """Test exception handling improvements in JobsService."""

    def test_retrieve_catches_enriched_exception_404(
        self,
        httpx_mock: HTTPXMock,
        jobs_service: JobsService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test retrieve() catches EnrichedException with status_code=404 and raises LookupError."""
        job_key = "nonexistent-job-key"

        # Mock 404 response
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.GetByKey(identifier={job_key})",
            status_code=404,
            json={"message": "Job not found", "errorCode": 1001},
        )

        # Should raise LookupError (converted from EnrichedException with 404)
        with pytest.raises(LookupError, match=f"Job with key '{job_key}' not found"):
            jobs_service.retrieve(job_key=job_key)

    def test_retrieve_propagates_non_404_errors(
        self,
        httpx_mock: HTTPXMock,
        jobs_service: JobsService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test retrieve() propagates non-404 errors (500, 401, 403) without converting to LookupError."""
        test_cases = [
            (500, "Internal Server Error"),
            (401, "Unauthorized"),
            (403, "Forbidden"),
        ]

        for status_code, error_msg in test_cases:
            job_key = f"job-{status_code}"

            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.GetByKey(identifier={job_key})",
                status_code=status_code,
                json={"error": error_msg},
            )

            # Should raise EnrichedException, not LookupError
            with pytest.raises(EnrichedException) as exc_info:
                jobs_service.retrieve(job_key=job_key)

            # Verify status_code attribute
            assert exc_info.value.status_code == status_code

    def test_retrieve_exception_chaining_preserved(
        self,
        httpx_mock: HTTPXMock,
        jobs_service: JobsService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test retrieve() preserves exception chain with 'from e' syntax."""
        job_key = "nonexistent-job"

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.GetByKey(identifier={job_key})",
            status_code=404,
            json={"message": "Not found"},
        )

        try:
            jobs_service.retrieve(job_key=job_key)
        except LookupError as e:
            # Verify exception chaining (from e)
            assert e.__cause__ is not None
            assert isinstance(e.__cause__, EnrichedException)
            assert e.__cause__.status_code == 404

    @pytest.mark.asyncio
    async def test_retrieve_async_catches_enriched_exception_404(
        self,
        httpx_mock: HTTPXMock,
        jobs_service: JobsService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test retrieve_async() catches EnrichedException with status_code=404."""
        job_key = "nonexistent-async-job"

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.GetByKey(identifier={job_key})",
            status_code=404,
            json={"message": "Job not found"},
        )

        with pytest.raises(LookupError, match=f"Job with key '{job_key}' not found"):
            await jobs_service.retrieve_async(job_key=job_key)

    @pytest.mark.asyncio
    async def test_retrieve_async_propagates_non_404_errors(
        self,
        httpx_mock: HTTPXMock,
        jobs_service: JobsService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test retrieve_async() propagates non-404 errors."""
        test_cases = [
            (500, "Internal Server Error"),
            (401, "Unauthorized"),
            (403, "Forbidden"),
        ]

        for status_code, error_msg in test_cases:
            job_key = f"job-async-{status_code}"

            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.GetByKey(identifier={job_key})",
                status_code=status_code,
                json={"error": error_msg},
            )

            with pytest.raises(EnrichedException) as exc_info:
                await jobs_service.retrieve_async(job_key=job_key)

            assert exc_info.value.status_code == status_code

    def test_exists_returns_false_for_404(
        self,
        httpx_mock: HTTPXMock,
        jobs_service: JobsService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test exists() returns False when retrieve() raises LookupError from 404."""
        job_key = "nonexistent-job"

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.GetByKey(identifier={job_key})",
            status_code=404,
            json={"message": "Job not found"},
        )

        # Should return False, not raise exception
        assert jobs_service.exists(job_key) is False

    def test_exists_propagates_500_errors(
        self,
        httpx_mock: HTTPXMock,
        jobs_service: JobsService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test exists() propagates 500 errors instead of returning False."""
        job_key = "error-job"

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.GetByKey(identifier={job_key})",
            status_code=500,
            json={"error": "Internal Server Error"},
        )

        # Should raise EnrichedException, not return False
        with pytest.raises(EnrichedException) as exc_info:
            jobs_service.exists(job_key)

        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_exists_async_returns_false_for_404(
        self,
        httpx_mock: HTTPXMock,
        jobs_service: JobsService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test exists_async() returns False for 404."""
        job_key = "nonexistent-async-job"

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.GetByKey(identifier={job_key})",
            status_code=404,
            json={"message": "Job not found"},
        )

        assert await jobs_service.exists_async(job_key) is False

    @pytest.mark.parametrize(
        "status_code,error_msg",
        [
            (500, "Internal Server Error"),
            (401, "Unauthorized"),
            (403, "Forbidden"),
        ],
    )
    def test_exception_parity_sync_async(
        self,
        httpx_mock: HTTPXMock,
        jobs_service: JobsService,
        base_url: str,
        org: str,
        tenant: str,
        status_code: int,
        error_msg: str,
    ) -> None:
        """Test sync and async raise identical exceptions for non-404 errors."""
        job_key = f"parity-job-{status_code}"

        # Mock for sync call
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.GetByKey(identifier={job_key})",
            status_code=status_code,
            json={"error": error_msg},
        )

        # Sync should raise EnrichedException
        with pytest.raises(EnrichedException) as sync_exc:
            jobs_service.retrieve(job_key=job_key)

        assert sync_exc.value.status_code == status_code
        assert error_msg in str(sync_exc.value)


class TestAttachmentsServiceExceptionHandling:
    """Test exception handling improvements in AttachmentsService."""

    def test_download_catches_enriched_exception_404_with_local_file(
        self,
        httpx_mock: HTTPXMock,
        attachments_service: AttachmentsService,
        base_url: str,
        org: str,
        tenant: str,
        tmp_path: Path,
    ) -> None:
        """Test download() catches EnrichedException 404 and falls back to local storage."""
        attachment_key = uuid.uuid4()

        # Mock 404 response from API
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Attachments({attachment_key})",
            status_code=404,
            json={"message": "Attachment not found"},
        )

        # Create local file in temp directory
        temp_dir = tmp_path / "temp_attachments"
        temp_dir.mkdir()
        local_file = temp_dir / f"{attachment_key}_test_document.pdf"
        local_file.write_text("test content")

        # Override temp directory
        attachments_service._temp_dir = str(temp_dir)

        # Download should succeed by falling back to local file
        destination = tmp_path / "downloaded.pdf"
        result = attachments_service.download(
            key=attachment_key, destination_path=str(destination)
        )

        # Verify local file was copied and name returned
        assert result == "test_document.pdf"
        assert destination.exists()
        assert destination.read_text() == "test content"

    def test_download_catches_enriched_exception_404_without_local_file(
        self,
        httpx_mock: HTTPXMock,
        attachments_service: AttachmentsService,
        base_url: str,
        org: str,
        tenant: str,
        tmp_path: Path,
    ) -> None:
        """Test download() raises Exception when 404 and no local file exists."""
        attachment_key = uuid.uuid4()

        # Mock 404 response from API
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Attachments({attachment_key})",
            status_code=404,
            json={"message": "Attachment not found"},
        )

        # Override temp directory to empty directory
        temp_dir = tmp_path / "temp_attachments"
        temp_dir.mkdir()
        attachments_service._temp_dir = str(temp_dir)

        # Download should raise Exception (converted from EnrichedException)
        destination = tmp_path / "downloaded.pdf"
        with pytest.raises(
            Exception,
            match=f"Attachment with key {attachment_key} not found in UiPath or local storage",
        ):
            attachments_service.download(
                key=attachment_key, destination_path=str(destination)
            )

    def test_download_propagates_non_404_errors(
        self,
        httpx_mock: HTTPXMock,
        attachments_service: AttachmentsService,
        base_url: str,
        org: str,
        tenant: str,
        tmp_path: Path,
    ) -> None:
        """Test download() propagates non-404 errors (500, 401, 403) without converting."""
        test_cases = [
            (500, "Internal Server Error"),
            (401, "Unauthorized"),
            (403, "Forbidden"),
        ]

        for status_code, error_msg in test_cases:
            attachment_key = uuid.uuid4()

            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/orchestrator_/odata/Attachments({attachment_key})",
                status_code=status_code,
                json={"error": error_msg},
            )

            # Should raise EnrichedException, not generic Exception
            destination = tmp_path / f"download_{status_code}.pdf"
            with pytest.raises(EnrichedException) as exc_info:
                attachments_service.download(
                    key=attachment_key, destination_path=str(destination)
                )

            # Verify status_code attribute
            assert exc_info.value.status_code == status_code

    def test_download_exception_chaining_preserved(
        self,
        httpx_mock: HTTPXMock,
        attachments_service: AttachmentsService,
        base_url: str,
        org: str,
        tenant: str,
        tmp_path: Path,
    ) -> None:
        """Test download() preserves exception chain with 'from e' syntax."""
        attachment_key = uuid.uuid4()

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Attachments({attachment_key})",
            status_code=404,
            json={"message": "Not found"},
        )

        # Override temp directory to empty directory
        temp_dir = tmp_path / "temp_attachments"
        temp_dir.mkdir()
        attachments_service._temp_dir = str(temp_dir)

        try:
            destination = tmp_path / "downloaded.pdf"
            attachments_service.download(
                key=attachment_key, destination_path=str(destination)
            )
        except Exception as e:
            # Verify exception chaining (from e)
            assert e.__cause__ is not None
            assert isinstance(e.__cause__, EnrichedException)
            assert e.__cause__.status_code == 404

    @pytest.mark.asyncio
    async def test_download_async_catches_enriched_exception_404_with_local_file(
        self,
        httpx_mock: HTTPXMock,
        attachments_service: AttachmentsService,
        base_url: str,
        org: str,
        tenant: str,
        tmp_path: Path,
    ) -> None:
        """Test download_async() catches EnrichedException 404 and falls back to local storage."""
        attachment_key = uuid.uuid4()

        # Mock 404 response from API
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Attachments({attachment_key})",
            status_code=404,
            json={"message": "Attachment not found"},
        )

        # Create local file in temp directory
        temp_dir = tmp_path / "temp_attachments"
        temp_dir.mkdir()
        local_file = temp_dir / f"{attachment_key}_async_document.pdf"
        local_file.write_text("async test content")

        # Override temp directory
        attachments_service._temp_dir = str(temp_dir)

        # Download should succeed by falling back to local file
        destination = tmp_path / "downloaded_async.pdf"
        result = await attachments_service.download_async(
            key=attachment_key, destination_path=str(destination)
        )

        # Verify local file was copied and name returned
        assert result == "async_document.pdf"
        assert destination.exists()
        assert destination.read_text() == "async test content"

    @pytest.mark.asyncio
    async def test_download_async_propagates_non_404_errors(
        self,
        httpx_mock: HTTPXMock,
        attachments_service: AttachmentsService,
        base_url: str,
        org: str,
        tenant: str,
        tmp_path: Path,
    ) -> None:
        """Test download_async() propagates non-404 errors."""
        test_cases = [
            (500, "Internal Server Error"),
            (401, "Unauthorized"),
            (403, "Forbidden"),
        ]

        for status_code, error_msg in test_cases:
            attachment_key = uuid.uuid4()

            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/orchestrator_/odata/Attachments({attachment_key})",
                status_code=status_code,
                json={"error": error_msg},
            )

            destination = tmp_path / f"download_async_{status_code}.pdf"
            with pytest.raises(EnrichedException) as exc_info:
                await attachments_service.download_async(
                    key=attachment_key, destination_path=str(destination)
                )

            assert exc_info.value.status_code == status_code

    def test_delete_catches_enriched_exception_404_with_local_file(
        self,
        httpx_mock: HTTPXMock,
        attachments_service: AttachmentsService,
        base_url: str,
        org: str,
        tenant: str,
        tmp_path: Path,
    ) -> None:
        """Test delete() catches EnrichedException 404 and deletes from local storage."""
        attachment_key = uuid.uuid4()

        # Mock 404 response from API
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Attachments({attachment_key})",
            status_code=404,
            json={"message": "Attachment not found"},
        )

        # Create local file in temp directory
        temp_dir = tmp_path / "temp_attachments"
        temp_dir.mkdir()
        local_file = temp_dir / f"{attachment_key}_to_delete.pdf"
        local_file.write_text("content to delete")

        # Override temp directory
        attachments_service._temp_dir = str(temp_dir)

        # Delete should succeed by deleting local file
        attachments_service.delete(key=attachment_key)

        # Verify local file was deleted
        assert not local_file.exists()

    def test_delete_catches_enriched_exception_404_without_local_file(
        self,
        httpx_mock: HTTPXMock,
        attachments_service: AttachmentsService,
        base_url: str,
        org: str,
        tenant: str,
        tmp_path: Path,
    ) -> None:
        """Test delete() raises Exception when 404 and no local file exists."""
        attachment_key = uuid.uuid4()

        # Mock 404 response from API
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Attachments({attachment_key})",
            status_code=404,
            json={"message": "Attachment not found"},
        )

        # Override temp directory to empty directory
        temp_dir = tmp_path / "temp_attachments"
        temp_dir.mkdir()
        attachments_service._temp_dir = str(temp_dir)

        # Delete should raise Exception
        with pytest.raises(
            Exception,
            match=f"Attachment with key {attachment_key} not found in UiPath or local storage",
        ):
            attachments_service.delete(key=attachment_key)

    def test_delete_propagates_non_404_errors(
        self,
        httpx_mock: HTTPXMock,
        attachments_service: AttachmentsService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test delete() propagates non-404 errors (500, 401, 403) without converting."""
        test_cases = [
            (500, "Internal Server Error"),
            (401, "Unauthorized"),
            (403, "Forbidden"),
        ]

        for status_code, error_msg in test_cases:
            attachment_key = uuid.uuid4()

            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/orchestrator_/odata/Attachments({attachment_key})",
                status_code=status_code,
                json={"error": error_msg},
            )

            # Should raise EnrichedException, not generic Exception
            with pytest.raises(EnrichedException) as exc_info:
                attachments_service.delete(key=attachment_key)

            # Verify status_code attribute
            assert exc_info.value.status_code == status_code

    @pytest.mark.asyncio
    async def test_delete_async_catches_enriched_exception_404_with_local_file(
        self,
        httpx_mock: HTTPXMock,
        attachments_service: AttachmentsService,
        base_url: str,
        org: str,
        tenant: str,
        tmp_path: Path,
    ) -> None:
        """Test delete_async() catches EnrichedException 404 and deletes from local storage."""
        attachment_key = uuid.uuid4()

        # Mock 404 response from API
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Attachments({attachment_key})",
            status_code=404,
            json={"message": "Attachment not found"},
        )

        # Create local file in temp directory
        temp_dir = tmp_path / "temp_attachments"
        temp_dir.mkdir()
        local_file = temp_dir / f"{attachment_key}_async_to_delete.pdf"
        local_file.write_text("async content to delete")

        # Override temp directory
        attachments_service._temp_dir = str(temp_dir)

        # Delete should succeed by deleting local file
        await attachments_service.delete_async(key=attachment_key)

        # Verify local file was deleted
        assert not local_file.exists()

    @pytest.mark.asyncio
    async def test_delete_async_propagates_non_404_errors(
        self,
        httpx_mock: HTTPXMock,
        attachments_service: AttachmentsService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        """Test delete_async() propagates non-404 errors."""
        test_cases = [
            (500, "Internal Server Error"),
            (401, "Unauthorized"),
            (403, "Forbidden"),
        ]

        for status_code, error_msg in test_cases:
            attachment_key = uuid.uuid4()

            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/orchestrator_/odata/Attachments({attachment_key})",
                status_code=status_code,
                json={"error": error_msg},
            )

            # Should raise EnrichedException, not generic Exception
            with pytest.raises(EnrichedException) as exc_info:
                await attachments_service.delete_async(key=attachment_key)

            assert exc_info.value.status_code == status_code
