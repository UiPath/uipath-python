"""API Calls testcase using live integration testing framework logic.

This testcase demonstrates various UiPath SDK API calls with automatic
resource cleanup similar to the live testing framework.

Usage:
    uv run uipath run main.py '{"message": "test"}'
"""

import logging
import os
import uuid
from dataclasses import dataclass

from dotenv import load_dotenv

from uipath import UiPath

logger = logging.getLogger(__name__)


def get_unique_name() -> str:
    """Generate unique name for test resources.

    Returns:
        Unique string in format 'test-{8-char-hex}'
    """
    return f"test-{uuid.uuid4().hex[:8]}"


def cleanup_resource(sdk: UiPath, resource_type: str, resource_id: str):
    """Clean up a resource after test.

    Args:
        sdk: UiPath SDK client
        resource_type: Type of resource (bucket, asset, etc.)
        resource_id: ID/name of resource to clean up
    """
    try:
        if resource_type == "bucket":
            logger.info(f"Cleaning up bucket: {resource_id}")
            try:
                # Delete all files in bucket first
                files = list(sdk.buckets.list_files(name=resource_id))
                for file in files:
                    try:
                        sdk.buckets.delete_file(name=resource_id, file_path=file.path)
                    except Exception as file_err:
                        logger.warning(
                            f"Could not delete file '{file.path}': {file_err}"
                        )
                # Now delete the bucket
                sdk.buckets.delete(name=resource_id)
            except Exception as e:
                logger.warning(f"Could not delete bucket '{resource_id}': {e}")
        elif resource_type == "asset":
            logger.info(f"Cleaning up asset: {resource_id}")
            try:
                sdk.assets.delete(name=resource_id)
            except Exception as e:
                logger.warning(f"Could not delete asset '{resource_id}': {e}")
        else:
            logger.warning(f"Unknown resource type '{resource_type}': {resource_id}")
    except Exception as e:
        logger.warning(
            f"Failed to cleanup {resource_type} '{resource_id}': {e}", exc_info=True
        )


def test_assets(sdk: UiPath, unique_name: str, cleanup_tracker: list[tuple[str, str]]):
    """Test Assets API - create and retrieve.

    Args:
        sdk: UiPath SDK client
        unique_name: Unique name prefix for resources
        cleanup_tracker: List to track resources for cleanup
    """
    asset_name = f"{unique_name}-asset"
    cleanup_tracker.append(("asset", asset_name))

    logger.info(f"Creating asset: {asset_name}")
    created_asset = sdk.assets.create(
        name=asset_name,
        value_type="Text",
        value="Test asset value from apicalls testcase",
        description="Test asset created by apicalls testcase",
    )

    logger.info(f"Asset created with ID: {created_asset.id}")
    assert created_asset.name == asset_name
    assert created_asset.id is not None

    # Retrieve the asset
    logger.info(f"Retrieving asset: {asset_name}")
    retrieved_asset = sdk.assets.retrieve(name=asset_name)
    assert retrieved_asset.name == asset_name
    assert retrieved_asset.id == created_asset.id
    logger.info("Asset retrieval successful!")


async def test_llm(sdk: UiPath):
    """Test LLM API - chat completions.

    Args:
        sdk: UiPath SDK client
    """
    messages = [
        {"role": "system", "content": "You are a helpful programming assistant."},
        {"role": "user", "content": "How do I read a file in Python?"},
        {"role": "assistant", "content": "You can use the built-in open() function."},
        {"role": "user", "content": "Can you show an example?"},
    ]

    # Test OpenAI-style API
    logger.info("Testing LLM OpenAI API...")
    result_openai = await sdk.llm_openai.chat_completions(messages)
    logger.info("LLM OpenAI Response: %s", result_openai.choices[0].message.content)
    assert result_openai.choices is not None
    assert len(result_openai.choices) > 0

    # Test normalized API
    logger.info("Testing LLM Normalized API...")
    result_normalized = await sdk.llm.chat_completions(messages)
    logger.info(
        "LLM Normalized Response: %s", result_normalized.choices[0].message.content
    )
    assert result_normalized.choices is not None
    assert len(result_normalized.choices) > 0


@dataclass
class EchoIn:
    message: str


@dataclass
class EchoOut:
    message: str


async def main(input: EchoIn) -> EchoOut:
    """Main entry point for the testcase.

    Args:
        input: Input data containing message

    Returns:
        Output data with message
    """
    # Load credentials from environment (like the fixtures do)
    load_dotenv()

    # Initialize SDK client
    sdk = UiPath()

    # Track resources for cleanup
    cleanup_tracker: list[tuple[str, str]] = []

    try:
        # Generate unique name for this run
        unique_name = get_unique_name()
        logger.info(f"Starting tests with unique name: {unique_name}")

        # Run tests
        logger.info("=== Testing Assets API ===")
        test_assets(sdk, unique_name, cleanup_tracker)

        logger.info("=== Testing LLM API ===")
        await test_llm(sdk)

        logger.info("=== All tests passed! ===")

    finally:
        # Clean up resources (in reverse order, like the fixture does)
        logger.info("=== Cleaning up resources ===")
        for resource_type, resource_id in reversed(cleanup_tracker):
            cleanup_resource(sdk, resource_type, resource_id)

        # Close the async client if needed
        if hasattr(sdk, "aclose"):
            await sdk.aclose()
        elif hasattr(sdk, "_async_client"):
            await sdk._async_client.aclose()

    return EchoOut(message=f"Tests completed: {input.message}")
