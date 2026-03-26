"""Integration tests for assets CLI commands.

These tests verify end-to-end functionality of the assets service commands,
including proper context handling, error messages, and output formatting.
"""

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from uipath._cli import cli
from uipath.platform.common.paging import PagedResult


@pytest.fixture
def runner():
    """Provide a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_client():
    """Provide a mocked UiPath client."""
    with patch("uipath.platform._uipath.UiPath") as mock:
        client_instance = MagicMock()
        mock.return_value = client_instance

        # Mock assets service
        client_instance.assets = MagicMock()

        yield client_instance


def test_assets_list_command_basic(runner, mock_client, mock_env_vars):
    """Test basic assets list command."""
    mock_assets = [
        MagicMock(
            name="asset1",
            value="value1",
            value_type="Text",
            model_dump=lambda: {
                "name": "asset1",
                "value": "value1",
                "valueType": "Text",
            },
        ),
        MagicMock(
            name="asset2",
            value="value2",
            value_type="Text",
            model_dump=lambda: {
                "name": "asset2",
                "value": "value2",
                "valueType": "Text",
            },
        ),
    ]
    mock_client.assets.list.return_value = PagedResult(
        items=mock_assets,
        has_more=False,
        skip=0,
        top=100,
    )

    result = runner.invoke(cli, ["assets", "list"])

    assert result.exit_code == 0
    assert "asset1" in result.output
    assert "asset2" in result.output


def test_assets_list_with_json_format(runner, mock_client, mock_env_vars):
    """Test assets list with JSON output format."""
    mock_assets = [
        MagicMock(model_dump=lambda: {"name": "test-asset", "value": "test-value"}),
    ]
    mock_client.assets.list.return_value = PagedResult(
        items=mock_assets,
        has_more=False,
        skip=0,
        top=100,
    )

    result = runner.invoke(cli, ["assets", "list", "--format", "json"])

    assert result.exit_code == 0
    assert "test-asset" in result.output


def test_assets_list_with_filter(runner, mock_client, mock_env_vars):
    """Test assets list with OData filter."""
    mock_assets = [
        MagicMock(model_dump=lambda: {"name": "text-asset", "valueType": "Text"}),
    ]
    mock_client.assets.list.return_value = PagedResult(
        items=mock_assets,
        has_more=False,
        skip=0,
        top=100,
    )

    result = runner.invoke(cli, ["assets", "list", "--filter", "ValueType eq 'Text'"])

    assert result.exit_code == 0
    mock_client.assets.list.assert_called_once()
    call_kwargs = mock_client.assets.list.call_args.kwargs
    assert call_kwargs["filter"] == "ValueType eq 'Text'"


def test_assets_list_with_orderby(runner, mock_client, mock_env_vars):
    """Test assets list with OData orderby."""
    mock_assets: list[MagicMock] = []
    mock_client.assets.list.return_value = PagedResult(
        items=mock_assets,
        has_more=False,
        skip=0,
        top=100,
    )

    result = runner.invoke(cli, ["assets", "list", "--orderby", "Name asc"])

    assert result.exit_code == 0
    call_kwargs = mock_client.assets.list.call_args.kwargs
    assert call_kwargs["orderby"] == "Name asc"


def test_assets_list_with_folder_path(runner, mock_client, mock_env_vars):
    """Test assets list with folder path option."""
    mock_assets: list[MagicMock] = []
    mock_client.assets.list.return_value = PagedResult(
        items=mock_assets,
        has_more=False,
        skip=0,
        top=100,
    )

    result = runner.invoke(cli, ["assets", "list", "--folder-path", "Shared"])

    assert result.exit_code == 0
    call_kwargs = mock_client.assets.list.call_args.kwargs
    assert call_kwargs["folder_path"] == "Shared"


def test_assets_help_text(runner):
    """Test that assets command has proper help text."""
    result = runner.invoke(cli, ["assets", "--help"])

    assert result.exit_code == 0
    assert "Manage UiPath assets" in result.output
    assert "list" in result.output


def test_assets_list_help_text(runner):
    """Test that assets list command has proper help text."""
    result = runner.invoke(cli, ["assets", "list", "--help"])

    assert result.exit_code == 0
    assert "List assets" in result.output
    assert "--folder-path" in result.output
    assert "--filter" in result.output
    assert "--orderby" in result.output
    assert "--top" in result.output
    assert "--skip" in result.output
