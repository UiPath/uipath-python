"""Utility functions for handling job attachments in evaluators."""

import re
import tempfile
import uuid
from pathlib import Path
from typing import Any

from ..models.models import UiPathEvaluationError, UiPathEvaluationErrorCategory


def is_job_attachment_uri(value: Any) -> bool:
    """Check if a value is a job attachment URI.

    Job attachment URIs follow the pattern:
    urn:uipath:cas:file:orchestrator:{attachment_id}

    Args:
        value: The value to check

    Returns:
        True if the value is a job attachment URI, False otherwise
    """
    if not isinstance(value, str):
        return False
    pattern = r"^urn:uipath:cas:file:orchestrator:([a-f0-9-]+)$"
    return bool(re.match(pattern, value, re.IGNORECASE))


def extract_attachment_id(uri: str) -> str:
    """Extract attachment ID from a job attachment URI.

    Args:
        uri: The job attachment URI

    Returns:
        The attachment ID (UUID)

    Raises:
        ValueError: If the URI is not a valid job attachment URI
    """
    pattern = r"^urn:uipath:cas:file:orchestrator:([a-f0-9-]+)$"
    match = re.match(pattern, uri, re.IGNORECASE)
    if match:
        return match.group(1)
    raise ValueError(f"Invalid job attachment URI: {uri}")


def download_attachment_as_string(attachment_id: str) -> str:
    """Download a job attachment and return its content as a string.

    Uses the AttachmentsService to download the file and reads it as a string.

    Args:
        attachment_id: The UUID of the attachment

    Returns:
        The file content as a string

    Raises:
        UiPathEvaluationError: If download fails or UiPath platform is not available
    """
    try:
        from uipath.platform import UiPath

        client = UiPath()

        # Create temporary file for download
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp_file:
            temp_path = tmp_file.name

        try:
            # Use AttachmentsService to download
            client.attachments.download(
                key=uuid.UUID(attachment_id), destination_path=temp_path
            )

            # Read and return content as string
            with open(temp_path, "r", encoding="utf-8") as f:
                return f.read()
        finally:
            # Clean up temporary file
            Path(temp_path).unlink(missing_ok=True)

    except Exception as e:
        raise UiPathEvaluationError(
            code="ATTACHMENT_DOWNLOAD_FAILED",
            title="Failed to download job attachment",
            detail=f"Could not download attachment {attachment_id}: {e}",
            category=UiPathEvaluationErrorCategory.SYSTEM,
        ) from e
