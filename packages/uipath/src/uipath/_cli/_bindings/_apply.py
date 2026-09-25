"""Shared scan-merge-write step behind `bindings generate` and `init`."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .._utils._console import ConsoleLogger
from ..models.runtime_schema import Bindings
from ._emitter import MergeReport, merge_bindings
from ._registry import build_registry
from ._scanner import SkippedReference, scan_project

console = ConsoleLogger()


@dataclass
class InferOutcome:
    """What a scan would change about a bindings file."""

    merged: Bindings
    report: MergeReport
    skipped: list[SkippedReference]

    @property
    def has_changes(self) -> bool:
        return bool(self.report.added)


def load_bindings(path: Path) -> Optional[Bindings]:
    """Read an existing bindings file, or None when there isn't one."""
    if not path.exists():
        return None
    try:
        return Bindings.model_validate_json(path.read_text())
    except ValueError as exc:
        console.error(f"Could not read '{path}': {exc}")


def serialize_bindings(bindings: Bindings) -> str:
    payload = bindings.model_dump(by_alias=True, exclude_none=True)
    return json.dumps(payload, indent=4)


def infer_bindings(root: Path, existing: Optional[Bindings]) -> InferOutcome:
    """Scan ``root`` and merge what it finds into ``existing``."""
    result = scan_project(root, build_registry())
    merged, report = merge_bindings(existing, result.references)
    return InferOutcome(merged=merged, report=report, skipped=result.skipped)


def report_outcome(outcome: InferOutcome) -> None:
    """Say what was found and, just as importantly, what was not."""
    for skipped in outcome.skipped:
        console.warning(f"{skipped.source}: {skipped.resource_type} — {skipped.reason}")
    for label in outcome.report.added:
        console.info(f"Discovered {label}")
    if outcome.report.preserved:
        console.info(
            f"Kept {len(outcome.report.preserved)} existing binding(s) "
            "not found in code."
        )


def infer_bindings_into_file(root: Path, bindings_path: Path) -> InferOutcome:
    """Scan, merge and write. Existing entries are never rewritten."""
    outcome = infer_bindings(root, load_bindings(bindings_path))
    report_outcome(outcome)
    if outcome.has_changes:
        bindings_path.write_text(serialize_bindings(outcome.merged))
        console.success(
            f"Recorded {len(outcome.report.added)} binding(s) in '{bindings_path}'."
        )
    else:
        console.info(f"No new bindings to record in '{bindings_path}'.")
    return outcome
