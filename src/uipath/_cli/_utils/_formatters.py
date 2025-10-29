"""Output formatting for different output modes.

This module provides consistent output formatting across all CLI commands,
supporting multiple formats (table, JSON, CSV) with proper handling of
Pydantic models, iterators, and large datasets.
"""

import csv
import json
from collections.abc import Generator, Iterator
from io import StringIO
from pathlib import Path
from typing import Any, Optional

import click


def format_output(
    data: Any,
    fmt: str = "table",
    output: Optional[str] = None,
    no_color: bool = False,
) -> None:
    """Format and output data to stdout or file.

    Handles:
    - Pydantic models (via model_dump())
    - Iterators and generators (converts to list)
    - Lists, dicts, primitives
    - Large datasets (warns at 10k+ items)

    Args:
        data: Data to format
        fmt: Output format (json, table, csv)
        output: Optional file path to write to
        no_color: Disable colored output for table format

    Example:
        >>> format_output([{"name": "bucket1"}, {"name": "bucket2"}], fmt="table")
        name
        --------
        bucket1
        bucket2
    """
    if isinstance(data, (Iterator, Generator)):
        data = list(data)
        # Warn about large datasets
        if len(data) > 10000:
            click.echo(
                f"Warning: Loading {len(data)} items into memory for formatting. "
                "This may be slow or cause memory issues. "
                "Consider using --limit or redirecting output for large datasets.",
                err=True,
            )

    if hasattr(data, "model_dump"):
        data = data.model_dump()
    elif isinstance(data, list) and len(data) > 0 and hasattr(data[0], "model_dump"):
        data = [item.model_dump() for item in data]

    if hasattr(data, "__aiter__"):
        raise TypeError(
            "Async iterators not supported in CLI output. "
            "Use synchronous methods or convert to list first."
        )

    if output and fmt == "table":
        no_color = True

    if fmt == "json":
        text = _format_json(data)
    elif fmt == "table":
        text = _format_table(data, no_color=no_color)
    elif fmt == "csv":
        text = _format_csv(data)
    else:
        text = str(data)

    if output:
        Path(output).write_text(text, encoding="utf-8")
        click.echo(f"Output written to {output}", err=True)
    else:
        click.echo(text)


def _format_json(data: Any) -> str:
    """Format data as JSON.

    Args:
        data: Data to format

    Returns:
        JSON string with 2-space indentation
    """
    return json.dumps(data, indent=2, default=str)


def _format_table(data: Any, no_color: bool = False) -> str:
    """Format data as table using rich (or simple fallback).

    Note: rich is required for full table formatting. If unavailable,
    a simple ASCII table fallback is used.

    Args:
        data: Data to format
        no_color: Disable colored output

    Returns:
        Formatted table string
    """
    items = data if isinstance(data, list) else [data]
    if not items:
        return "No results"

    if not isinstance(items[0], dict):
        items = [{"value": str(item)} for item in items]

    columns = list(items[0].keys())

    try:
        from rich.console import Console
        from rich.table import Table

        table = Table(show_header=True, header_style="bold")
        for col in columns:
            table.add_column(col)

        for item in items:
            table.add_row(*[str(item.get(col, "")) for col in columns])

        buffer = StringIO()
        console = Console(file=buffer, force_terminal=not no_color)
        console.print(table)

        return buffer.getvalue()

    except ImportError:
        header = " | ".join(columns)
        separator = "-" * len(header)
        rows = [" | ".join(str(item.get(col, "")) for col in columns) for item in items]
        return "\n".join([header, separator, *rows])


def _format_csv(data: Any) -> str:
    """Format data as CSV.

    Args:
        data: Data to format

    Returns:
        CSV string with header
    """
    items = data if isinstance(data, list) else [data]
    if not items:
        return ""

    if not isinstance(items[0], dict):
        items = [{"value": str(item)} for item in items]

    columns = list(items[0].keys())

    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()

    for item in items:
        normalized_row = {col: item.get(col, "") for col in columns}
        writer.writerow(normalized_row)

    return output.getvalue()
