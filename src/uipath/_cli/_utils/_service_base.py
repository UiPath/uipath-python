"""Base utilities for service commands.

This module provides decorators and utilities for implementing service-specific
CLI commands with consistent error handling, async support, and output formatting.

Key features:
- Sequential decorator composition
- Type-safe context access
- Enhanced Click exception handling
- Async/await support
- Consistent error messages
"""

import asyncio
import inspect
from functools import wraps
from typing import Any, Callable

import click
from httpx import HTTPError

from ...models.errors import BaseUrlMissingError, SecretMissingError
from ...models.exceptions import EnrichedException
from ._context import get_cli_context


def handle_not_found_error(
    resource: str, identifier: str, error: Exception | None = None
) -> None:
    """Handle 404/LookupError and raise consistent ClickException.

    Args:
        resource: The resource type (e.g., "Bucket", "Asset", "Queue")
        identifier: The resource identifier (name, key, etc.)
        error: Optional original error for chaining

    Raises:
        click.ClickException: Always raises with consistent message
    """
    message = f"{resource} '{identifier}' not found."
    if error:
        raise click.ClickException(message) from error
    else:
        raise click.ClickException(message) from None


def service_command(f: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator for service commands with async support, error handling, and output.

    This decorator handles:
    - Sync and async function execution
    - Output formatting (JSON, table, CSV)
    - Error handling with proper Click exceptions
    - Separation of logs (stderr) from data (stdout)
    - Type-safe context access via get_cli_context()
    - Enhanced Click exception handling (don't catch Click's own exceptions)
    - Domain errors converted to click.ClickException
    - Automatic context injection (no need for @click.pass_context)

    Example:
        >>> @buckets.command()
        >>> @service_command
        >>> async def list_async(ctx):
        ...     # Context is automatically passed - no @click.pass_context needed
        ...     return await client.buckets.list_async()

    Note:
        Do NOT stack @click.pass_context with this decorator - context is
        already injected by the @wraps(f) and @click.pass_context inside
        service_command.
    """

    @wraps(f)
    @click.pass_context
    def wrapper(ctx, *args, **kwargs):
        cli_ctx = get_cli_context(ctx)

        try:
            result = f(ctx, *args, **kwargs)

            if inspect.isawaitable(result):
                try:
                    result = asyncio.run(result)  # type: ignore[arg-type]
                except RuntimeError as e:
                    if "cannot be called from a running event loop" in str(e).lower():
                        prev_loop = asyncio.get_event_loop()
                        if prev_loop.is_running():
                            loop = asyncio.new_event_loop()
                            try:
                                asyncio.set_event_loop(loop)
                                result = loop.run_until_complete(result)
                            finally:
                                try:
                                    loop.close()
                                finally:
                                    asyncio.set_event_loop(prev_loop)
                        else:
                            result = prev_loop.run_until_complete(result)
                    else:
                        raise

            # Format and output result
            if result is not None:
                from ._formatters import format_output

                fmt = kwargs.get("format") or cli_ctx.output_format
                output = kwargs.get("output")

                format_output(
                    result,
                    fmt=fmt,
                    output=output,
                    no_color=False,  # Auto-detected for file output
                )

            return result

        except click.ClickException:
            raise

        except BaseUrlMissingError:
            raise click.ClickException(
                "UIPATH_URL not configured. Set the UIPATH_URL environment variable or run 'uipath auth'."
            ) from None

        except SecretMissingError:
            raise click.ClickException(
                "Authentication required. Set the UIPATH_ACCESS_TOKEN environment variable or run 'uipath auth'."
            ) from None

        except EnrichedException as e:
            if cli_ctx.debug:
                raise

            if e.status_code == 401:
                raise click.ClickException(
                    "Authentication failed (401). Your access token may have expired or is invalid.\n"
                    "Please run 'uipath auth' to re-authenticate."
                ) from e

            if e.status_code == 400:
                try:
                    import json

                    error_data = json.loads(e.response_content)
                    if (
                        isinstance(error_data, dict)
                        and error_data.get("errorCode") == 1101
                    ):
                        raise click.ClickException(
                            "Folder context required (400). The command requires a folder to be specified.\n"
                            'Set UIPATH_FOLDER_PATH environment variable (e.g., export UIPATH_FOLDER_PATH="Shared") '
                            'or use the --folder-path option (e.g., --folder-path "Shared").'
                        ) from e
                except (ValueError, json.JSONDecodeError):
                    pass

            raise click.ClickException(str(e)) from e

        except HTTPError as e:
            if cli_ctx.debug:
                raise
            response = getattr(e, "response", None)

            if response and response.status_code == 401:
                raise click.ClickException(
                    "Authentication failed (401). Your access token may have expired or is invalid.\n"
                    "Please run 'uipath auth' to re-authenticate."
                ) from e

            if response and response.status_code == 400:
                try:
                    error_data = response.json()
                    if (
                        isinstance(error_data, dict)
                        and error_data.get("errorCode") == 1101
                    ):
                        raise click.ClickException(
                            "Folder context required (400). The command requires a folder to be specified.\n"
                            'Set UIPATH_FOLDER_PATH environment variable (e.g., export UIPATH_FOLDER_PATH="Shared") '
                            'or use the --folder-path option (e.g., --folder-path "Shared").'
                        ) from e
                except ValueError:
                    pass

            if response:
                error_msg = f"HTTP Error {response.status_code}: {response.url}"
                if hasattr(response, "text"):
                    try:
                        import json

                        response_data = response.json()
                        sensitive_fields = {
                            "access_token",
                            "refresh_token",
                            "password",
                            "secret",
                            "api_key",
                            "authorization",
                        }
                        if isinstance(response_data, dict):
                            for key in list(response_data.keys()):
                                if any(
                                    sensitive in key.lower()
                                    for sensitive in sensitive_fields
                                ):
                                    response_data[key] = "***REDACTED***"
                        error_details = json.dumps(response_data, indent=2)
                        error_msg += f"\nResponse:\n{error_details[:500]}"
                    except Exception:
                        error_msg += f"\nResponse: {response.text[:200]}"
            else:
                error_msg = f"HTTP Error: {str(e)}"
            raise click.ClickException(error_msg) from e

        except Exception as e:
            if cli_ctx.debug:
                raise
            raise click.ClickException(str(e)) from e

    return wrapper


def common_service_options(f: Callable[..., Any]) -> Callable[..., Any]:
    """Add common options for service commands.

    Adds:
    - --folder-path: Folder path (e.g., "Shared") with validation
    - --folder-key: Folder key (UUID) with validation
    - --format: Output format override
    - --output: Output file override
    """
    from ._validators import validate_folder_path, validate_uuid

    decorators = [
        click.option(
            "--folder-path",
            callback=validate_folder_path,
            help='Folder path (e.g., "Shared"). Can also be set via UIPATH_FOLDER_PATH environment variable.',
        ),
        click.option("--folder-key", callback=validate_uuid, help="Folder key (UUID)"),
        click.option(
            "--format",
            type=click.Choice(["json", "table", "csv"]),
            help="Output format (overrides global)",
        ),
        click.option(
            "--output", "-o", type=click.Path(), help="Output file (overrides global)"
        ),
    ]

    for decorator in reversed(decorators):
        f = decorator(f)

    return f


def standard_service_command(f: Callable[..., Any]) -> Callable[..., Any]:
    """Convenience decorator for standard service commands.

    This composes decorators in explicit, sequential order:
    1. service_command (execution & error handling)
    2. common_service_options (folder, format, output)

    The sequential pattern makes the decorator stack more readable
    and easier for AI agents to understand.

    Usage:
        >>> # Simple command
        >>> @buckets.command()
        >>> @standard_service_command
        >>> def retrieve(ctx, name, folder_path, ...):
        ...     pass

        >>> # Custom composition (when you need flexibility)
        >>> @buckets.command()
        >>> @service_command
        >>> @click.option('--custom-flag', ...)
        >>> @common_service_options
        >>> @click.pass_context
        >>> def special(ctx, custom_flag, ...):
        ...     pass
    """
    decorated_func = f

    decorated_func = service_command(decorated_func)

    decorated_func = common_service_options(decorated_func)

    return decorated_func


class ServiceCommandBase:
    """Base class for service command utilities."""

    @staticmethod
    def get_client(ctx):
        """Get or create UiPath client from context.

        This caches the client in the CLI context to avoid recreating
        it for every command invocation.

        Args:
            ctx: Click context

        Returns:
            UiPath client instance

        Raises:
            click.ClickException: If required environment variables are not set
        """
        import os

        import click

        cli_ctx = get_cli_context(ctx)

        if cli_ctx._client is None:
            from ..._uipath import UiPath

            base_url = os.environ.get("UIPATH_URL")
            secret = os.environ.get("UIPATH_ACCESS_TOKEN")

            if not base_url:
                raise click.ClickException(
                    "UIPATH_URL not configured. Set the UIPATH_URL environment variable or run 'uipath auth'."
                )

            if not secret:
                raise click.ClickException(
                    "Authentication required. Set the UIPATH_ACCESS_TOKEN environment variable or run 'uipath auth'."
                )

            cli_ctx._client = UiPath(
                base_url=base_url,
                secret=secret,
                debug=cli_ctx.debug,
            )

        return cli_ctx._client
