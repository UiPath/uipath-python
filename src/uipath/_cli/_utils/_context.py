"""Type-safe context management for Click commands.

This module provides type-safe access to CLI context across all commands,
improving developer experience and enabling better IDE autocomplete.
"""

from dataclasses import dataclass, field
from typing import Any, Optional, cast

import click


@dataclass
class CliContext:
    """CLI global context object.

    This provides type-safe access to configuration shared across all commands.
    Using a dataclass ensures all attributes are properly typed and documented.

    Attributes:
        default_folder: Default folder path for operations
        output_format: Output format (table, json, csv)
        debug: Enable debug logging

    Note:
        Authentication (URL and secret) are always read from environment variables
        (UIPATH_URL and UIPATH_ACCESS_TOKEN).
    """

    default_folder: Optional[str] = None
    output_format: str = "table"
    debug: bool = False

    # Client cache - initialized on first access
    _client: Any = field(default=None, init=False, repr=False)


def get_cli_context(ctx: click.Context) -> CliContext:
    """Type-safe helper to retrieve CliContext from Click context.

    This eliminates repeated cast() calls and provides autocompletion
    for CLI context attributes.

    Args:
        ctx: Click context object

    Returns:
        Typed CliContext object

    Example:
        >>> @buckets.command()
        >>> @click.pass_context
        >>> def list(ctx):
        ...     cli_ctx = get_cli_context(ctx)  # Fully typed!
        ...     print(cli_ctx.default_folder)  # Autocomplete works
    """
    return cast(CliContext, ctx.obj)


# Optional: Idiomatic Click decorator alternative
# This can be used as @pass_cli_context decorator on commands
# for even cleaner code
pass_cli_context = click.make_pass_decorator(CliContext, ensure=True)
