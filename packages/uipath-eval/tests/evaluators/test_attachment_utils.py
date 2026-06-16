"""Tests for attachment utility functions."""

import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from uipath.eval.evaluators.attachment_utils import (
    download_attachment_as_string,
    extract_attachment_id,
    is_job_attachment_uri,
)
from uipath.eval.models.models import UiPathEvaluationError


class TestIsJobAttachmentUri:
    """Tests for is_job_attachment_uri function."""

    def test_valid_attachment_uri_lowercase(self):
        """Test with valid attachment URI in lowercase."""
        uri = "urn:uipath:cas:file:orchestrator:123e4567-e89b-12d3-a456-426614174000"
        assert is_job_attachment_uri(uri) is True

    def test_valid_attachment_uri_uppercase(self):
        """Test with valid attachment URI in uppercase."""
        uri = "urn:uipath:cas:file:orchestrator:123E4567-E89B-12D3-A456-426614174000"
        assert is_job_attachment_uri(uri) is True

    def test_valid_attachment_uri_mixed_case(self):
        """Test with valid attachment URI in mixed case."""
        uri = "URN:UIPATH:CAS:FILE:ORCHESTRATOR:123e4567-E89B-12d3-A456-426614174000"
        assert is_job_attachment_uri(uri) is True

    def test_invalid_uri_wrong_prefix(self):
        """Test with wrong URI prefix."""
        uri = "urn:uipath:cas:file:other:123e4567-e89b-12d3-a456-426614174000"
        assert is_job_attachment_uri(uri) is False

    def test_invalid_uri_malformed_uuid(self):
        """Test with malformed UUID."""
        uri = "urn:uipath:cas:file:orchestrator:not-a-uuid"
        assert is_job_attachment_uri(uri) is False

    def test_invalid_uri_missing_parts(self):
        """Test with missing URI parts."""
        uri = "urn:uipath:cas:file:123e4567-e89b-12d3-a456-426614174000"
        assert is_job_attachment_uri(uri) is False

    def test_non_string_value_dict(self):
        """Test with non-string value (dict)."""
        assert is_job_attachment_uri({"key": "value"}) is False

    def test_non_string_value_int(self):
        """Test with non-string value (int)."""
        assert is_job_attachment_uri(123) is False

    def test_non_string_value_none(self):
        """Test with None value."""
        assert is_job_attachment_uri(None) is False

    def test_empty_string(self):
        """Test with empty string."""
        assert is_job_attachment_uri("") is False

    def test_regular_file_path(self):
        """Test with regular file path."""
        assert is_job_attachment_uri("/path/to/file.txt") is False


class TestExtractAttachmentId:
    """Tests for extract_attachment_id function."""

    def test_extract_valid_uuid_lowercase(self):
        """Test extracting UUID from valid URI (lowercase)."""
        uri = "urn:uipath:cas:file:orchestrator:123e4567-e89b-12d3-a456-426614174000"
        result = extract_attachment_id(uri)
        assert result == "123e4567-e89b-12d3-a456-426614174000"

    def test_extract_valid_uuid_uppercase(self):
        """Test extracting UUID from valid URI (uppercase)."""
        uri = "urn:uipath:cas:file:orchestrator:123E4567-E89B-12D3-A456-426614174000"
        result = extract_attachment_id(uri)
        assert result == "123E4567-E89B-12D3-A456-426614174000"

    def test_extract_valid_uuid_mixed_case(self):
        """Test extracting UUID from valid URI (mixed case)."""
        uri = "URN:UIPATH:CAS:FILE:ORCHESTRATOR:aB3e4567-E89B-12d3-A456-426614174000"
        result = extract_attachment_id(uri)
        assert result == "aB3e4567-E89B-12d3-A456-426614174000"

    def test_invalid_uri_raises_error(self):
        """Test that invalid URI raises ValueError."""
        uri = "urn:uipath:cas:file:other:123e4567-e89b-12d3-a456-426614174000"
        with pytest.raises(ValueError, match="Invalid job attachment URI"):
            extract_attachment_id(uri)

    def test_malformed_uuid_raises_error(self):
        """Test that malformed UUID raises ValueError."""
        uri = "urn:uipath:cas:file:orchestrator:not-a-uuid"
        with pytest.raises(ValueError, match="Invalid job attachment URI"):
            extract_attachment_id(uri)

    def test_empty_string_raises_error(self):
        """Test that empty string raises ValueError."""
        with pytest.raises(ValueError, match="Invalid job attachment URI"):
            extract_attachment_id("")


class TestDownloadAttachmentAsString:
    """Tests for download_attachment_as_string function."""

    def test_successful_download(self):
        """Test successful attachment download."""
        attachment_id = "123e4567-e89b-12d3-a456-426614174000"
        expected_content = "This is the attachment content"

        # Create a mock UiPath client
        mock_client = MagicMock()
        mock_attachments = MagicMock()
        mock_client.attachments = mock_attachments

        # Mock the download method to write content to the temp file
        def mock_download(key, destination_path):
            with open(destination_path, "w", encoding="utf-8") as f:
                f.write(expected_content)

        mock_attachments.download.side_effect = mock_download

        with patch("uipath.platform.UiPath", return_value=mock_client):
            result = download_attachment_as_string(attachment_id)

        assert result == expected_content
        mock_attachments.download.assert_called_once()

        # Verify UUID was passed correctly
        call_args = mock_attachments.download.call_args
        assert call_args.kwargs["key"] == uuid.UUID(attachment_id)
        assert "destination_path" in call_args.kwargs

    def test_download_with_multiline_content(self):
        """Test downloading attachment with multiline content."""
        attachment_id = "123e4567-e89b-12d3-a456-426614174000"
        expected_content = "Line 1\nLine 2\nLine 3"

        mock_client = MagicMock()
        mock_attachments = MagicMock()
        mock_client.attachments = mock_attachments

        def mock_download(key, destination_path):
            with open(destination_path, "w", encoding="utf-8") as f:
                f.write(expected_content)

        mock_attachments.download.side_effect = mock_download

        with patch("uipath.platform.UiPath", return_value=mock_client):
            result = download_attachment_as_string(attachment_id)

        assert result == expected_content
        assert "\n" in result
        assert result.count("\n") == 2

    def test_download_failure_raises_evaluation_error(self):
        """Test that download failure raises UiPathEvaluationError."""
        attachment_id = "123e4567-e89b-12d3-a456-426614174000"

        mock_client = MagicMock()
        mock_attachments = MagicMock()
        mock_client.attachments = mock_attachments
        mock_attachments.download.side_effect = Exception("Network error")

        with patch("uipath.platform.UiPath", return_value=mock_client):
            with pytest.raises(UiPathEvaluationError) as exc_info:
                download_attachment_as_string(attachment_id)

        assert exc_info.value.error_info.code == "Python.ATTACHMENT_DOWNLOAD_FAILED"
        assert "Failed to download job attachment" in exc_info.value.error_info.title
        assert "Network error" in exc_info.value.error_info.detail

    def test_temp_file_cleanup_on_success(self):
        """Test that temporary file is cleaned up after successful download."""
        attachment_id = "123e4567-e89b-12d3-a456-426614174000"
        temp_files_created = []

        mock_client = MagicMock()
        mock_attachments = MagicMock()
        mock_client.attachments = mock_attachments

        def mock_download(key, destination_path):
            temp_files_created.append(destination_path)
            with open(destination_path, "w", encoding="utf-8") as f:
                f.write("content")

        mock_attachments.download.side_effect = mock_download

        with patch("uipath.platform.UiPath", return_value=mock_client):
            download_attachment_as_string(attachment_id)

        # Verify temp file was cleaned up
        assert len(temp_files_created) == 1
        assert not Path(temp_files_created[0]).exists()

    def test_temp_file_cleanup_on_failure(self):
        """Test that temporary file is cleaned up even on failure."""
        attachment_id = "123e4567-e89b-12d3-a456-426614174000"
        temp_files_created = []

        mock_client = MagicMock()
        mock_attachments = MagicMock()
        mock_client.attachments = mock_attachments

        def mock_download(key, destination_path):
            temp_files_created.append(destination_path)
            # Create the file but then raise an error
            with open(destination_path, "w", encoding="utf-8") as f:
                f.write("partial content")
            raise Exception("Download failed midway")

        mock_attachments.download.side_effect = mock_download

        with patch("uipath.platform.UiPath", return_value=mock_client):
            with pytest.raises(UiPathEvaluationError):
                download_attachment_as_string(attachment_id)

        # Verify temp file was cleaned up
        assert len(temp_files_created) == 1
        assert not Path(temp_files_created[0]).exists()

    def test_uipath_client_import_error(self):
        """Test handling when UiPath client cannot be imported."""
        attachment_id = "123e4567-e89b-12d3-a456-426614174000"

        with patch(
            "uipath.platform.UiPath",
            side_effect=ImportError("Module not found"),
        ):
            with pytest.raises(UiPathEvaluationError) as exc_info:
                download_attachment_as_string(attachment_id)

        assert exc_info.value.error_info.code == "Python.ATTACHMENT_DOWNLOAD_FAILED"
        assert "Module not found" in exc_info.value.error_info.detail
