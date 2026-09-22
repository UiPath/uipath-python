"""Static discovery of resource references in a project's Python sources.

The scan is deliberately conservative. It reports a reference only when it can
see which SDK method is being called and which argument carries the resource
name; everything else is reported as skipped so the gap is visible rather than
guessed at.
"""

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ._registry import BindingSpec, service_attributes

EXCLUDED_DIR_NAMES = frozenset(
    {
        ".git",
        ".hg",
        ".idea",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".uipath",
        ".venv",
        ".vscode",
        "__pycache__",
        "build",
        "dist",
        "env",
        "node_modules",
        "site-packages",
        "test",
        "tests",
        "venv",
    }
)


@dataclass(frozen=True)
class ResourceReference:
    """A resource the agent code refers to."""

    resource_type: str
    name: str
    name_is_expression: bool
    folder_path: Optional[str]
    folder_is_expression: bool
    activity_name: str
    source: str


@dataclass(frozen=True)
class SkippedReference:
    """A call that touches a resource but could not be turned into a binding."""

    resource_type: str
    reason: str
    source: str


@dataclass
class ScanResult:
    references: list[ResourceReference] = field(default_factory=list)
    skipped: list[SkippedReference] = field(default_factory=list)

    def extend(self, other: "ScanResult") -> None:
        self.references.extend(other.references)
        self.skipped.extend(other.skipped)

    def deduplicated(self) -> "ScanResult":
        seen: dict[tuple[str, str, Optional[str]], ResourceReference] = {}
        for reference in self.references:
            key = (reference.resource_type, reference.name, reference.folder_path)
            seen.setdefault(key, reference)
        return ScanResult(references=list(seen.values()), skipped=self.skipped)


def _is_excluded_file(path: Path) -> bool:
    return path.name.startswith("test_") or path.name.endswith("_test.py")


def iter_project_files(root: Path) -> list[Path]:
    """Project sources worth scanning, in a stable order."""
    files: list[Path] = []
    for path in sorted(root.rglob("*.py")):
        relative = path.relative_to(root)
        if any(part in EXCLUDED_DIR_NAMES for part in relative.parts[:-1]):
            continue
        if _is_excluded_file(path):
            continue
        files.append(path)
    return files


def _module_constants(tree: ast.Module) -> dict[str, str]:
    """Module-level ``NAME = "literal"`` assignments, minus anything reassigned."""
    constants: dict[str, str] = {}
    reassigned: set[str] = set()
    for node in tree.body:
        targets: list[ast.expr] = []
        value: Optional[ast.expr] = None
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
            value = node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets = [node.target]
            value = node.value
        for target in targets:
            if not isinstance(target, ast.Name):
                continue
            if target.id in constants or target.id in reassigned:
                reassigned.add(target.id)
                constants.pop(target.id, None)
                continue
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                constants[target.id] = value.value
    return constants


def _resolve(node: ast.expr, constants: dict[str, str]) -> tuple[str, bool]:
    """Return the value and whether it had to be kept as an expression."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value, False
    if isinstance(node, ast.Name) and node.id in constants:
        return constants[node.id], False
    return ast.unparse(node), True


def _argument(
    call: ast.Call, param: Optional[str], index: Optional[int]
) -> Optional[ast.expr]:
    if param is None:
        return None
    for keyword in call.keywords:
        if keyword.arg == param:
            return keyword.value
    if index is not None and len(call.args) > index:
        argument = call.args[index]
        if isinstance(argument, ast.Starred):
            return None
        return argument
    return None


def _spec_for_call(
    call: ast.Call, registry: dict[tuple[str, str], BindingSpec], services: set[str]
) -> Optional[BindingSpec]:
    if not isinstance(call.func, ast.Attribute):
        return None
    owner = call.func.value
    if not isinstance(owner, ast.Attribute):
        return None
    if owner.attr not in services:
        return None
    return registry.get((owner.attr, call.func.attr))


def scan_tree(
    tree: ast.Module, path_label: str, registry: dict[tuple[str, str], BindingSpec]
) -> ScanResult:
    result = ScanResult()
    services = service_attributes(registry)
    constants = _module_constants(tree)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        spec = _spec_for_call(node, registry, services)
        if spec is None:
            continue

        source = f"{path_label}:{node.lineno}"
        name_node = _argument(node, spec.name_param, spec.name_index)
        if name_node is None:
            result.skipped.append(
                SkippedReference(
                    resource_type=spec.resource_type,
                    reason=(
                        f"could not determine '{spec.name_param}' for "
                        f"{spec.service_attr}.{spec.method}"
                    ),
                    source=source,
                )
            )
            continue

        name, name_is_expression = _resolve(name_node, constants)
        folder_node = _argument(node, spec.folder_param, spec.folder_index)
        if folder_node is None:
            folder_path, folder_is_expression = None, False
        else:
            folder_path, folder_is_expression = _resolve(folder_node, constants)

        result.references.append(
            ResourceReference(
                resource_type=spec.resource_type,
                name=name,
                name_is_expression=name_is_expression,
                folder_path=folder_path,
                folder_is_expression=folder_is_expression,
                activity_name=spec.activity_name,
                source=source,
            )
        )
    return result


def scan_source(
    source: str, path_label: str, registry: dict[tuple[str, str], BindingSpec]
) -> ScanResult:
    """Scan a single in-memory module."""
    return scan_tree(ast.parse(source), path_label, registry).deduplicated()


def scan_project(
    root: Path, registry: dict[tuple[str, str], BindingSpec]
) -> ScanResult:
    """Scan every project source file under ``root``."""
    combined = ScanResult()
    for path in iter_project_files(root):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue
        label = path.relative_to(root).as_posix()
        combined.extend(scan_tree(tree, label, registry))
    return combined.deduplicated()
