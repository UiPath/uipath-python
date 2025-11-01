"""Pytest configuration and fixtures for live integration tests."""

import logging
import os
import uuid
from typing import AsyncGenerator, Generator

import pytest
from dotenv import load_dotenv

from uipath import UiPath

logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def credentials() -> dict[str, str]:
    """Load and validate credentials from environment.

    Returns:
        Dictionary with url, token, and folder

    Raises:
        pytest.fail: If credentials are missing in CI environment
        pytest.skip: If credentials are missing in local environment
    """
    load_dotenv()

    url = os.getenv("UIPATH_URL")
    token = os.getenv("UIPATH_ACCESS_TOKEN")
    folder = os.getenv("UIPATH_FOLDER_PATH") or "Shared"

    if not url or not token:
        is_ci = os.getenv("CI") == "true" or os.getenv("GITHUB_ACTIONS") == "true"

        if is_ci:
            pytest.fail(
                "Missing UIPATH credentials in CI environment. "
                "Check GitHub secrets: UIPATH_URL, UIPATH_ACCESS_TOKEN"
            )
        else:
            pytest.skip(
                "Missing UIPATH credentials. "
                "Run 'uipath auth' or set environment variables: "
                "UIPATH_URL, UIPATH_ACCESS_TOKEN"
            )

    return {"url": url, "token": token, "folder": folder}


@pytest.fixture
async def uipath_client(credentials: dict[str, str]) -> AsyncGenerator[UiPath, None]:
    """Provide authenticated UiPath client with managed async lifecycle.

    This fixture is function-scoped to ensure the httpx AsyncClient
    is created and destroyed within the same event loop, preventing
    "Event loop is closed" errors when running async tests in a suite.

    Args:
        credentials: Validated credentials from credentials fixture

    Yields:
        Authenticated UiPath SDK client instance

    Note:
        pytest-asyncio automatically runs this async fixture for both
        sync and async tests, so no changes are needed to existing tests.
    """
    # Set all credential environment variables before creating client
    os.environ["UIPATH_URL"] = credentials["url"]
    os.environ["UIPATH_ACCESS_TOKEN"] = credentials["token"]
    if "folder" in credentials:
        os.environ["UIPATH_FOLDER_PATH"] = credentials["folder"]

    client = UiPath()
    yield client

    # Ensure the underlying httpx AsyncClient is closed before event loop closes
    # NOTE: We intentionally use _async_client as a fallback for cleanup.
    # This is necessary because the SDK may not expose a public aclose() method yet.
    # TODO: Replace with public API when UiPath SDK adds formal async context manager support
    if hasattr(client, "aclose"):
        await client.aclose()
    elif hasattr(client, "_async_client"):
        # Access private attribute for cleanup - this is acceptable in test fixtures
        # where we need to ensure proper resource cleanup to prevent event loop errors
        await client._async_client.aclose()


@pytest.fixture
def unique_name() -> str:
    """Generate unique name for test resources.

    Returns:
        Unique string in format 'test-{8-char-hex}'
    """
    return f"test-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def cleanup_tracker(
    uipath_client: UiPath,
) -> Generator[list[tuple[str, str]], None, None]:
    """Track resources created during test for cleanup (sync tests only).

    Yields:
        List of (resource_type, resource_id) tuples for cleanup

    Example:
        >>> def test_example(cleanup_tracker):
        ...     cleanup_tracker.append(("bucket", "test-bucket-name"))
        ...     # Resources will be cleaned up after test

    Note:
        For async tests, use async_cleanup_tracker instead to avoid event loop conflicts.

    Supported resource types (Phase 1):
        - "bucket": Bucket name (will be retrieved and deleted by ID)

    Phase 2+ will add:
        - "asset": Asset name
        - "queue": Queue name
    """
    resources: list[tuple[str, str]] = []
    yield resources

    for resource_type, resource_id in reversed(resources):
        try:
            if resource_type == "bucket":
                logger.info(f"Cleaning up bucket: {resource_id}")
                # Delete all files in bucket first, then delete bucket
                try:
                    # List and delete all files in the bucket
                    try:
                        files = list(uipath_client.buckets.list_files(name=resource_id))
                        for file in files:
                            try:
                                uipath_client.buckets.delete_file(
                                    name=resource_id, file_path=file.path
                                )
                            except Exception as file_err:
                                logger.warning(
                                    f"Could not delete file '{file.path}' from bucket '{resource_id}': {file_err}"
                                )
                    except Exception as list_err:
                        logger.warning(
                            f"Could not list files in bucket '{resource_id}': {list_err}"
                        )

                    # Now delete the bucket
                    uipath_client.buckets.delete(name=resource_id)
                except Exception as e:
                    logger.warning(
                        f"Could not delete bucket '{resource_id}' by name: {e}"
                    )
            else:
                logger.warning(
                    f"Unknown resource type '{resource_type}' for cleanup: {resource_id}"
                )
        except Exception as e:
            logger.warning(
                f"Failed to cleanup {resource_type} '{resource_id}': {e}",
                exc_info=True,
            )


@pytest.fixture
async def async_cleanup_tracker(
    uipath_client: UiPath,
) -> AsyncGenerator[list[tuple[str, str]], None]:
    """Track resources created during async test for cleanup.

    Yields:
        List of (resource_type, resource_id) tuples for cleanup

    Example:
        >>> async def test_example(async_cleanup_tracker):
        ...     async_cleanup_tracker.append(("bucket", "test-bucket-name"))
        ...     # Resources will be cleaned up after test

    Note:
        This async version ensures cleanup runs within the test's event loop,
        preventing "Event loop is closed" errors.

    Supported resource types (Phase 1):
        - "bucket": Bucket name (will be deleted using async method)

    Phase 2+ will add:
        - "asset": Asset name
        - "queue": Queue name
    """
    resources: list[tuple[str, str]] = []
    yield resources

    for resource_type, resource_id in reversed(resources):
        try:
            if resource_type == "bucket":
                logger.info(f"Cleaning up bucket (async): {resource_id}")
                # Delete all files in bucket first, then delete bucket (async)
                try:
                    # List and delete all files in the bucket
                    try:
                        files = [
                            f
                            async for f in uipath_client.buckets.list_files_async(
                                name=resource_id
                            )
                        ]
                        for file in files:
                            try:
                                await uipath_client.buckets.delete_file_async(
                                    name=resource_id, file_path=file.path
                                )
                            except Exception as file_err:
                                logger.warning(
                                    f"Could not delete file '{file.path}' from bucket '{resource_id}' (async): {file_err}"
                                )
                    except Exception as list_err:
                        logger.warning(
                            f"Could not list files in bucket '{resource_id}' (async): {list_err}"
                        )

                    # Now delete the bucket
                    await uipath_client.buckets.delete_async(name=resource_id)
                except Exception as e:
                    logger.warning(
                        f"Could not delete bucket '{resource_id}' by name (async): {e}"
                    )
            else:
                logger.warning(
                    f"Unknown resource type '{resource_type}' for async cleanup: {resource_id}"
                )
        except Exception as e:
            logger.warning(
                f"Failed to cleanup {resource_type} '{resource_id}' (async): {e}",
                exc_info=True,
            )
