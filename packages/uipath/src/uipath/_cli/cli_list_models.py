from collections.abc import Iterable

import click
from rich.console import Console
from rich.table import Table

from ..platform.agenthub import LlmModel
from ._utils._context import get_cli_context
from ._utils._service_base import ServiceCommandBase, service_command


@click.command(name="list-models")
@click.option(
    "--format",
    type=click.Choice(["json", "table", "csv"]),
    help="Output format (overrides global)",
)
@click.option(
    "--output",
    "--output-file",
    "-o",
    type=click.Path(),
    help="File path where the output will be written",
)
@service_command
async def list_models(ctx, format, output):
    """List available LLM models."""
    client = ServiceCommandBase.get_client(ctx)
    models = await client.agenthub.get_available_llm_models_async()

    fmt = format or get_cli_context(ctx).output_format
    if fmt == "table" and not output:
        _render_rich_table(models)
        return None
    return models


def _render_rich_table(models: Iterable[LlmModel]) -> None:
    """Render models as a rich table with one column per vendor."""
    by_vendor: dict[str, list[str]] = {}
    for model in models:
        vendor = model.vendor or "Unknown"
        by_vendor.setdefault(vendor, []).append(model.model_name)

    console = Console()
    if not by_vendor:
        console.print("Available LLM Models: none")
        return

    for names in by_vendor.values():
        names.sort()

    vendors = sorted(by_vendor.keys())

    table = Table(title="Available LLM Models", show_lines=False)
    for vendor in vendors:
        table.add_column(vendor, style="cyan", no_wrap=True)

    max_rows = max(len(by_vendor[v]) for v in vendors)
    for i in range(max_rows):
        row = [by_vendor[v][i] if i < len(by_vendor[v]) else "" for v in vendors]
        table.add_row(*row)

    console.print(table)
