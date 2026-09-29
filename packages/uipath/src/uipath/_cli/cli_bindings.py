"""CLI commands for working with the project's resource bindings."""

from pathlib import Path

import click

from uipath.platform.common import UiPathConfig

from ._bindings._apply import (
    infer_bindings,
    load_bindings,
    report_outcome,
    serialize_bindings,
)
from ._telemetry import track_command
from ._utils._console import ConsoleLogger

console = ConsoleLogger()


@click.group()
def bindings() -> None:
    r"""Inspect and generate resource bindings.

    \b
    Examples:
        uipath bindings generate
        uipath bindings generate --dry-run
        uipath bindings generate --check
    """
    pass


@bindings.command(name="generate")
@click.argument(
    "root",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=Path("."),
    metavar="",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would change without writing the file.",
)
@click.option(
    "--check",
    is_flag=True,
    help="Exit non-zero if bindings.json is missing entries. Writes nothing.",
)
@track_command("bindings_generate")
def generate(root: Path, dry_run: bool, check: bool) -> None:
    """Generate bindings.json from the resources referenced in your code.

    Scans the project's Python sources for UiPath SDK calls that take a
    resource name, and records each one as a binding so it can be remapped at
    deployment. Discovery is best effort: a resource whose name is built at
    runtime is reported rather than guessed, and entries already in the file
    are never modified.

    Test files and virtual environments are not scanned.

    **Example:**

        $ uipath bindings generate
        $ uipath bindings generate --check
    """
    bindings_path = root / UiPathConfig.bindings_file_path
    existing = load_bindings(bindings_path)
    outcome = infer_bindings(root, existing)
    report_outcome(outcome)

    if check:
        if outcome.has_changes:
            console.error(
                f"'{bindings_path}' is missing {len(outcome.report.added)} "
                "binding(s). Run 'uipath bindings generate'."
            )
        console.success(f"'{bindings_path}' is up to date.")
        return

    if dry_run:
        console.info(f"Would write {len(outcome.merged.resources)} binding(s):")
        click.echo(serialize_bindings(outcome.merged))
        return

    if not outcome.has_changes and existing is not None:
        console.success(f"'{bindings_path}' is up to date.")
        return

    bindings_path.write_text(serialize_bindings(outcome.merged))
    console.success(
        f"Wrote '{bindings_path}' with {len(outcome.merged.resources)} binding(s) "
        f"({len(outcome.report.added)} new)."
    )

    if outcome.skipped:
        console.hint(
            f"{len(outcome.skipped)} resource call(s) could not be resolved "
            "statically. Add those bindings by hand if they need remapping."
        )
