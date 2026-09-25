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

from ._interrupts import INTERRUPT_SPECS, InterruptSpec
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


def _binding_counts(tree: ast.Module) -> dict[str, int]:
    """Count every place a name is bound, at any depth.

    Augmented assignment, a rebind inside a branch or loop, a function-local of
    the same name: all of them mean the value at the call site may not be the
    literal seen at module level.
    """
    counts: dict[str, int] = {}

    def bump(name: str) -> None:
        counts[name] = counts.get(name, 0) + 1

    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            bump(node.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bump(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                bump(alias.asname or alias.name.split(".")[0])
    return counts


def _module_constants(tree: ast.Module) -> dict[str, str]:
    """Module-level ``NAME = "literal"`` assignments that are never rebound."""
    counts = _binding_counts(tree)
    constants: dict[str, str] = {}
    for node in tree.body:
        targets: list[ast.expr]
        value: ast.expr
        if isinstance(node, ast.Assign):
            targets, value = list(node.targets), node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value = [node.target], node.value
        else:
            continue
        if not (isinstance(value, ast.Constant) and isinstance(value.value, str)):
            continue
        for target in targets:
            if isinstance(target, ast.Name) and counts.get(target.id) == 1:
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


def _uipath_imports(tree: ast.Module) -> set[str]:
    """Local names bound by an import from a ``uipath`` module.

    An interrupt model is matched by class name, which is generic enough
    (``CreateTask``) to collide with unrelated code, so only names that
    demonstrably came from the SDK are considered.
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "uipath" or module.startswith("uipath."):
                for alias in node.names:
                    names.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "uipath" or alias.name.startswith("uipath."):
                    names.add(alias.asname or alias.name.split(".")[0])
    return names


def _interrupt_spec_for_call(
    call: ast.Call, imported: set[str]
) -> Optional[InterruptSpec]:
    """Match ``InvokeProcess(...)`` or ``interrupt_models.InvokeProcess(...)``."""
    if isinstance(call.func, ast.Name):
        attribute, owner = call.func.id, call.func.id
    elif isinstance(call.func, ast.Attribute):
        attribute = call.func.attr
        owner_node = call.func.value
        if not isinstance(owner_node, ast.Name):
            return None
        owner = owner_node.id
    else:
        return None
    if owner not in imported:
        return None
    return INTERRUPT_SPECS.get(attribute)


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


def _record(
    result: ScanResult,
    node: ast.Call,
    source: str,
    constants: dict[str, str],
    *,
    resource_type: str,
    name_param: str,
    name_index: Optional[int],
    folder_param: Optional[str],
    folder_index: Optional[int],
    activity_name: str,
    origin: str,
) -> None:
    """Turn one matched call into a reference, or a skip with a reason."""
    name_node = _argument(node, name_param, name_index)
    if name_node is None:
        result.skipped.append(
            SkippedReference(
                resource_type=resource_type,
                reason=f"could not determine '{name_param}' for {origin}",
                source=source,
            )
        )
        return

    name, name_is_expression = _resolve(name_node, constants)
    folder_node = _argument(node, folder_param, folder_index)
    if folder_node is None:
        folder_path, folder_is_expression = None, False
    else:
        folder_path, folder_is_expression = _resolve(folder_node, constants)

    result.references.append(
        ResourceReference(
            resource_type=resource_type,
            name=name,
            name_is_expression=name_is_expression,
            folder_path=folder_path,
            folder_is_expression=folder_is_expression,
            activity_name=activity_name,
            source=source,
        )
    )


def scan_tree(
    tree: ast.Module, path_label: str, registry: dict[tuple[str, str], BindingSpec]
) -> ScanResult:
    """Find resource references in one module, by either matching rule."""
    result = ScanResult()
    services = service_attributes(registry)
    constants = _module_constants(tree)
    imported = _uipath_imports(tree)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        source = f"{path_label}:{node.lineno}"

        spec = _spec_for_call(node, registry, services)
        if spec is not None:
            _record(
                result,
                node,
                source,
                constants,
                resource_type=spec.resource_type,
                name_param=spec.name_param,
                name_index=spec.name_index,
                folder_param=spec.folder_param,
                folder_index=spec.folder_index,
                activity_name=spec.activity_name,
                origin=f"{spec.service_attr}.{spec.method}",
            )
            continue

        interrupt = _interrupt_spec_for_call(node, imported)
        if interrupt is not None:
            _record(
                result,
                node,
                source,
                constants,
                resource_type=interrupt.resource_type,
                name_param=interrupt.name_field,
                name_index=None,
                folder_param=interrupt.folder_field,
                folder_index=None,
                activity_name=interrupt.activity_name,
                origin=interrupt.model,
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
