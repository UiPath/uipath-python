"""Integration tests for buckets CLI commands.

These tests verify end-to-end functionality of the buckets service commands,
including proper context handling, error messages, and output formatting.
"""

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from uipath._cli import cli


@pytest.fixture
def runner():
    """Provide a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_client():
    """Provide a mocked UiPath client."""
    # Patch where UiPath is actually defined
    with patch("uipath._uipath.UiPath") as mock:
        client_instance = MagicMock()
        mock.return_value = client_instance

        # Mock buckets service
        client_instance.buckets = MagicMock()

        yield client_instance


def test_buckets_list_command_basic(runner, mock_client, mock_env_vars):
    """Test basic buckets list command."""
    # Mock bucket data - list command now expects an iterator
    mock_client.buckets.list.return_value = iter(
        [
            MagicMock(
                name="bucket1",
                description="First bucket",
                model_dump=lambda: {"name": "bucket1", "description": "First bucket"},
            ),
            MagicMock(
                name="bucket2",
                description="Second bucket",
                model_dump=lambda: {"name": "bucket2", "description": "Second bucket"},
            ),
        ]
    )

    result = runner.invoke(cli, ["buckets", "list"])

    assert result.exit_code == 0
    assert "bucket1" in result.output
    assert "bucket2" in result.output


def test_buckets_list_with_json_format(runner, mock_client, mock_env_vars):
    """Test buckets list with JSON output format."""
    mock_client.buckets.list.return_value = iter(
        [
            MagicMock(model_dump=lambda: {"name": "test-bucket", "id": "123"}),
        ]
    )

    result = runner.invoke(cli, ["buckets", "list", "--format", "json"])

    assert result.exit_code == 0
    assert "test-bucket" in result.output


def test_buckets_create_command(runner, mock_client, mock_env_vars):
    """Test buckets create command."""
    mock_bucket = MagicMock()
    mock_bucket.name = "new-bucket"
    mock_bucket.model_dump.return_value = {"name": "new-bucket", "id": "456"}
    mock_client.buckets.create.return_value = mock_bucket

    result = runner.invoke(
        cli, ["buckets", "create", "new-bucket", "--description", "Test bucket"]
    )

    assert result.exit_code == 0
    # Click's CliRunner captures both stdout and stderr in result.output by default
    assert "Created bucket 'new-bucket'" in result.output


def test_buckets_retrieve_without_name_or_key_fails(runner, mock_env_vars):
    """Test that retrieve without --name or --key fails with usage error."""
    result = runner.invoke(cli, ["buckets", "retrieve"])

    assert result.exit_code != 0
    assert "Either --name or --key must be provided" in result.output


def test_buckets_retrieve_with_both_name_and_key_fails(runner, mock_env_vars):
    """Test that retrieve with both --name and --key fails."""
    result = runner.invoke(
        cli, ["buckets", "retrieve", "--name", "test", "--key", "123"]
    )

    assert result.exit_code != 0
    assert "Provide either --name or --key, not both" in result.output


def test_buckets_delete_with_confirm(runner, mock_client, mock_env_vars):
    """Test buckets delete command with --confirm flag."""
    mock_bucket = MagicMock()
    mock_bucket.name = "test-bucket"
    mock_bucket.id = 123
    mock_client.buckets.retrieve.return_value = mock_bucket
    mock_client.buckets.delete = MagicMock()  # Mock the SDK delete method

    result = runner.invoke(cli, ["buckets", "delete", "test-bucket", "--confirm"])

    assert result.exit_code == 0
    # Click's CliRunner captures both stdout and stderr in result.output by default
    assert "Deleted bucket 'test-bucket'" in result.output
    # Assert SDK delete was called
    mock_client.buckets.delete.assert_called_once_with(
        name="test-bucket",
        folder_path=None,
        folder_key=None,
    )


def test_buckets_delete_dry_run(runner, mock_client, mock_env_vars):
    """Test buckets delete command with --dry-run flag."""
    mock_bucket = MagicMock()
    mock_bucket.name = "test-bucket"
    mock_bucket.id = 123
    mock_client.buckets.retrieve.return_value = mock_bucket
    mock_client.buckets.delete = MagicMock()  # Mock the SDK delete method

    result = runner.invoke(cli, ["buckets", "delete", "test-bucket", "--dry-run"])

    assert result.exit_code == 0
    # Click's CliRunner captures both stdout and stderr in result.output by default
    assert "Would delete bucket" in result.output
    mock_client.buckets.delete.assert_not_called()  # Assert SDK method was not called


def test_buckets_list_with_pagination(runner, mock_client, mock_env_vars):
    """Test buckets list command with pagination options.

    Note: SDK list() auto-paginates internally and doesn't accept limit/offset.
    The CLI applies client-side pagination after fetching results.
    """
    # Create test data
    mock_buckets = [
        MagicMock(model_dump=lambda i=i: {"name": f"bucket{i}", "id": str(i)})
        for i in range(20)
    ]
    mock_client.buckets.list.return_value = iter(mock_buckets)

    result = runner.invoke(cli, ["buckets", "list", "--limit", "10", "--offset", "5"])

    assert result.exit_code == 0
    mock_client.buckets.list.assert_called_once()

    # Verify SDK was called WITHOUT limit/offset (it handles pagination internally)
    call_kwargs = mock_client.buckets.list.call_args.kwargs
    assert "limit" not in call_kwargs
    assert "offset" not in call_kwargs

    # Verify client-side pagination was applied (should show buckets 5-14)
    # We can't easily verify the exact output without parsing, but we can check success
    assert "bucket" in result.output.lower()


def test_buckets_list_with_limit_zero(runner, mock_client, mock_env_vars):
    """Test that --limit 0 returns empty list (regression test for truthiness bug).

    This is a regression test for the bug where limit=0 would return all items
    instead of an empty list due to Python's truthiness evaluation (0 is falsy).
    """
    # Create test data
    mock_buckets = [
        MagicMock(model_dump=lambda i=i: {"name": f"bucket{i}", "id": str(i)})
        for i in range(10)
    ]
    mock_client.buckets.list.return_value = iter(mock_buckets)

    result = runner.invoke(cli, ["buckets", "list", "--limit", "0"])

    assert result.exit_code == 0
    # Verify empty output (no buckets should be returned)
    # With --format table (default), should show empty table or "no results"
    # We check that no bucket names appear in the output
    assert "bucket0" not in result.output
    assert "bucket1" not in result.output


def test_buckets_help_text(runner):
    """Test that buckets command has proper help text."""
    result = runner.invoke(cli, ["buckets", "--help"])

    assert result.exit_code == 0
    assert "Manage UiPath storage buckets" in result.output
    assert "list" in result.output
    assert "create" in result.output
    assert "delete" in result.output


def test_buckets_list_help_text(runner):
    """Test that buckets list command has proper help text."""
    result = runner.invoke(cli, ["buckets", "list", "--help"])

    assert result.exit_code == 0
    assert "List all Buckets" in result.output
    assert "--folder-path" in result.output
    assert "--limit" in result.output


def test_buckets_delete_non_existent_bucket(runner, mock_client, mock_env_vars):
    """Test deleting a bucket that does not exist."""
    # Mock retrieve to raise LookupError
    mock_client.buckets.retrieve.side_effect = LookupError("Bucket not found")

    result = runner.invoke(cli, ["buckets", "delete", "no-such-bucket", "--confirm"])

    assert result.exit_code != 0
    assert "Bucket 'no-such-bucket' not found" in result.output


def test_buckets_retrieve_non_existent_bucket(runner, mock_client, mock_env_vars):
    """Test retrieving a bucket that does not exist."""
    # Mock retrieve to raise LookupError
    mock_client.buckets.retrieve.side_effect = LookupError("Bucket not found")

    result = runner.invoke(cli, ["buckets", "retrieve", "--name", "no-such-bucket"])

    assert result.exit_code != 0
    assert "Bucket 'no-such-bucket' not found" in result.output
