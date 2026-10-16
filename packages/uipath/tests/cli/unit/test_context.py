"""Unit tests for type-safe context management.

Tests the CliContext dataclass and get_cli_context() helper.
"""

import click
from click.testing import CliRunner

from uipath._cli._utils._console import OutputMode
from uipath._cli._utils._context import CliContext, get_cli_context


def test_cli_context_default_values():
    """Test that CliContext has sensible default values."""
    ctx = CliContext()

    assert ctx.output_mode is OutputMode.TEXT
    assert ctx.debug is False
    assert ctx._client is None


def test_cli_context_with_values():
    """Test that CliContext accepts custom values."""
    ctx = CliContext(
        output_mode=OutputMode.JSON,
        debug=True,
    )

    assert ctx.output_mode is OutputMode.JSON
    assert ctx.debug is True


def test_get_cli_context_returns_typed_object():
    """Test that get_cli_context returns a typed CliContext object."""

    @click.command()
    @click.pass_context
    def test_cmd(ctx):
        cli_ctx = get_cli_context(ctx)
        assert isinstance(cli_ctx, CliContext)
        assert hasattr(cli_ctx, "output_mode")
        assert hasattr(cli_ctx, "debug")

    # Create a Click context with CliContext
    runner = CliRunner()
    ctx_obj = CliContext(output_mode=OutputMode.JSON)

    with runner.isolated_filesystem():
        result = runner.invoke(test_cmd, obj=ctx_obj)
        assert result.exit_code == 0


def test_cli_context_is_dataclass():
    """Test that CliContext is a proper dataclass."""
    import dataclasses

    assert dataclasses.is_dataclass(CliContext)

    # Test that we can use dataclass features
    ctx1 = CliContext(output_mode=OutputMode.JSON, debug=True)
    ctx2 = CliContext(output_mode=OutputMode.JSON, debug=True)

    # Dataclasses with same values should be equal
    assert ctx1 == ctx2


def test_cli_context_client_cache():
    """Test that _client field is properly initialized."""
    ctx = CliContext()

    # Should start as None
    assert ctx._client is None

    # Should be able to set it
    mock_client = object()
    ctx._client = mock_client
    assert ctx._client is mock_client
