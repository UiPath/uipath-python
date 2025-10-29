"""Common validators for CLI commands.

This module provides reusable validation functions for common CLI inputs
like folder paths, UUIDs, and resource names.
"""

import re
from typing import Optional

import click


def validate_folder_path(ctx, param, value: Optional[str]) -> Optional[str]:
    """Validate folder path format.

    Folder paths should be in the format: "Folder1/Subfolder2"

    Args:
        ctx: Click context
        param: Click parameter
        value: Folder path to validate

    Returns:
        Validated folder path

    Raises:
        click.BadParameter: If folder path is invalid
    """
    if value is None:
        return None

    if value == "":
        return value

    if value.startswith("/") or value.endswith("/"):
        raise click.BadParameter("Folder path should not start or end with '/'")

    return value


def validate_uuid(ctx, param, value: Optional[str]) -> Optional[str]:
    """Validate UUID format.

    Args:
        ctx: Click context
        param: Click parameter
        value: UUID to validate

    Returns:
        Validated UUID

    Raises:
        click.BadParameter: If UUID is invalid
    """
    if value is None:
        return None

    # UUID regex pattern
    uuid_pattern = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
    )

    if not uuid_pattern.match(value):
        raise click.BadParameter(
            f"'{value}' is not a valid UUID. "
            "Expected format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
        )

    return value


def validate_resource_name(ctx, param, value: Optional[str]) -> Optional[str]:
    """Validate resource name.

    Resource names should:
    - Not be empty
    - Not contain special characters that might cause issues

    Args:
        ctx: Click context
        param: Click parameter
        value: Resource name to validate

    Returns:
        Validated resource name

    Raises:
        click.BadParameter: If resource name is invalid
    """
    if value is None:
        return None

    if not value.strip():
        raise click.BadParameter("Resource name cannot be empty")

    invalid_chars = ["<", ">", ":", '"', "|", "?", "*"]
    for char in invalid_chars:
        if char in value:
            raise click.BadParameter(
                f"Resource name contains invalid character: '{char}'"
            )

    return value


def validate_mutually_exclusive(ctx, param, value, exclusive_with: str):
    """Validate that two options are mutually exclusive.

    Args:
        ctx: Click context
        param: Click parameter
        value: Current parameter value (can be any type)
        exclusive_with: Name of the mutually exclusive parameter

    Returns:
        Validated value

    Raises:
        click.UsageError: If both parameters are provided
    """
    if value is not None and ctx.params.get(exclusive_with) is not None:
        raise click.UsageError(
            f"--{param.name} and --{exclusive_with} are mutually exclusive. "
            "Provide only one."
        )

    return value
