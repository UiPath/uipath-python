"""AST-based call graph builder for Python function runtimes.

Parses user code starting from an entrypoint function and builds a
UiPathRuntimeGraph of function call relationships. Only follows calls
into local project files (skips external dependencies).

Node IDs use the "file:line" format so they can double as breakpoint
locations for the debug runtime.
"""

from __future__ import annotations

import ast
import logging
import os
from pathlib import Path

from uipath.runtime.schema import (
    UiPathRuntimeEdge,
    UiPathRuntimeGraph,
    UiPathRuntimeNode,
)

logger = logging.getLogger(__name__)

DEFAULT_MAX_DEPTH = 3


def build_call_graph(
    file_path: str,
    function_name: str,
    *,
    project_dir: str | None = None,
    max_depth: int = DEFAULT_MAX_DEPTH,
) -> UiPathRuntimeGraph:
    """Build a call graph starting from *function_name* in *file_path*.

    Parameters
    ----------
    file_path:
        Absolute or relative path to the Python source file containing the
        entrypoint function.
    function_name:
        Name of the entrypoint function inside *file_path*.
    project_dir:
        Root directory of the project. Only files under this directory are
        followed. Defaults to the parent of *file_path*.
    max_depth:
        Maximum recursion depth for following function calls.

    UiPathRuntimeGraph
        A graph with nodes (id="relative/path.py:line") and edges
        representing call relationships.
    """
    abs_file = os.path.abspath(file_path)
    if project_dir is None:
        project_dir = str(Path(abs_file).parent)
    project_dir = os.path.abspath(project_dir)

    ctx = _BuildContext(project_dir=project_dir, max_depth=max_depth)
    ctx.visit_function(abs_file, function_name, depth=0)
    return UiPathRuntimeGraph(nodes=ctx.nodes, edges=ctx.edges)


class _BuildContext:
    """Accumulates nodes and edges while walking the call graph."""

    def __init__(self, project_dir: str, max_depth: int) -> None:
        self.project_dir = project_dir
        self.max_depth = max_depth
        self.nodes: list[UiPathRuntimeNode] = []
        self.edges: list[UiPathRuntimeEdge] = []
        self._visited: set[str] = set()  # node IDs already processed
        self._ast_cache: dict[str, ast.Module] = {}

    def _parse_file(self, abs_path: str) -> ast.Module | None:
        """Parse a Python file, returning the cached AST or None on failure."""
        if abs_path in self._ast_cache:
            return self._ast_cache[abs_path]
        try:
            with open(abs_path, encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=abs_path)
            self._ast_cache[abs_path] = tree
            return tree
        except Exception:
            logger.debug("Failed to parse %s", abs_path, exc_info=True)
            return None

    def _relative_path(self, abs_path: str) -> str:
        """Return a forward-slash relative path from the project dir."""
        try:
            return str(Path(abs_path).relative_to(self.project_dir)).replace("\\", "/")
        except ValueError:
            return Path(abs_path).name

    def _node_id(self, abs_path: str, line: int) -> str:
        return f"{self._relative_path(abs_path)}:{line}"

    def _is_project_file(self, abs_path: str) -> bool:
        return abs_path.startswith(self.project_dir) and "site-packages" not in abs_path

    def _find_function_def(
        self, tree: ast.Module, name: str
    ) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
        """Find a top-level function definition by name."""
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == name:
                    return node
        return None

    def _resolve_imports(
        self, tree: ast.Module, abs_file: str
    ) -> dict[str, _ImportInfo]:
        """Build a map of imported names → their source locations.

        Only resolves imports that point to local project files.
        """
        result: dict[str, _ImportInfo] = {}
        file_dir = os.path.dirname(abs_file)

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ImportFrom):
                module_path = self._resolve_module_path(
                    node.module, node.level, file_dir
                )
                if module_path is None or not self._is_project_file(module_path):
                    continue
                for alias in node.names:
                    imported_name = alias.asname if alias.asname else alias.name
                    result[imported_name] = _ImportInfo(
                        abs_path=module_path,
                        original_name=alias.name,
                    )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    module_path = self._resolve_module_path(alias.name, 0, file_dir)
                    if module_path is None or not self._is_project_file(module_path):
                        continue
                    local_name = alias.asname if alias.asname else alias.name
                    result[local_name] = _ImportInfo(
                        abs_path=module_path,
                        original_name=None,  # module-level import
                    )
        return result

    def _resolve_module_path(
        self, module: str | None, level: int, file_dir: str
    ) -> str | None:
        """Resolve a module name to an absolute file path, or None."""
        if module is None and level == 0:
            return None

        if level > 0:
            # Relative import: go up (level - 1) directories from file_dir
            base = file_dir
            for _ in range(level - 1):
                base = os.path.dirname(base)
            if module:
                parts = module.split(".")
                candidate = os.path.join(base, *parts)
            else:
                candidate = base
        else:
            # Absolute import: try from project dir
            parts = module.split(".")  # type: ignore[union-attr]
            candidate = os.path.join(self.project_dir, *parts)

        # Check file.py then package/__init__.py
        as_file = candidate + ".py"
        if os.path.isfile(as_file):
            return os.path.abspath(as_file)

        as_pkg = os.path.join(candidate, "__init__.py")
        if os.path.isfile(as_pkg):
            return os.path.abspath(as_pkg)

        return None

    def _collect_calls(
        self, func_node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> list[_CallSite]:
        """Walk the function body and collect all function call sites."""
        calls: list[_CallSite] = []
        for node in ast.walk(func_node):
            if not isinstance(node, ast.Call):
                continue
            info = self._extract_call_info(node)
            if info is not None:
                calls.append(info)
        return calls

    def _extract_call_info(self, call_node: ast.Call) -> _CallSite | None:
        """Extract the callable name and line from a Call AST node."""
        func = call_node.func
        line = call_node.lineno

        if isinstance(func, ast.Name):
            # Simple call: foo()
            return _CallSite(name=func.id, attr=None, line=line)
        elif isinstance(func, ast.Attribute):
            # Attribute call: module.foo() or obj.method()
            if isinstance(func.value, ast.Name):
                return _CallSite(name=func.value.id, attr=func.attr, line=line)
        return None

    @staticmethod
    def _first_body_line(
        func_def: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> int:
        """Return the line number of the first executable statement in the body.

        Skips leading docstrings so the resulting line sits *inside* the
        function, not on the ``def`` line.  This matters for breakpoints:
        a ``def`` line is a module-level statement executed during import,
        whereas the first body line only fires when the function is called.
        """
        for stmt in func_def.body:
            # Skip docstring (Expr wrapping a Constant string)
            if (
                isinstance(stmt, ast.Expr)
                and isinstance(stmt.value, ast.Constant)
                and isinstance(stmt.value.value, str)
            ):
                continue
            return stmt.lineno
        # Fallback: function has only a docstring (or is empty)
        return func_def.body[0].lineno if func_def.body else func_def.lineno

    def visit_function(self, abs_file: str, func_name: str, depth: int) -> str | None:
        """Process a function: create its node and recurse into its calls.

        Returns the node ID if the function was found, otherwise None.
        """
        tree = self._parse_file(abs_file)
        if tree is None:
            return None

        func_def = self._find_function_def(tree, func_name)
        if func_def is None:
            return None

        node_id = self._node_id(abs_file, self._first_body_line(func_def))

        # Add node even if already visited (we need the ID for edges)
        if node_id in self._visited:
            return node_id

        self._visited.add(node_id)
        self.nodes.append(
            UiPathRuntimeNode(
                id=node_id,
                name=func_name,
                type="function",
                metadata={"file": self._relative_path(abs_file)},
            )
        )

        if depth >= self.max_depth:
            return node_id

        # Resolve imports and local definitions
        imports = self._resolve_imports(tree, abs_file)
        local_funcs = self._collect_local_function_names(tree)
        calls = self._collect_calls(func_def)

        for call in calls:
            target_id = self._resolve_and_visit_call(
                call, abs_file, tree, imports, local_funcs, depth
            )
            if target_id is not None:
                self.edges.append(UiPathRuntimeEdge(source=node_id, target=target_id))

        return node_id

    def _collect_local_function_names(self, tree: ast.Module) -> set[str]:
        """Collect names of all top-level functions defined in a module."""
        names: set[str] = set()
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                names.add(node.name)
        return names

    def _resolve_and_visit_call(
        self,
        call: _CallSite,
        caller_file: str,
        caller_tree: ast.Module,
        imports: dict[str, _ImportInfo],
        local_funcs: set[str],
        depth: int,
    ) -> str | None:
        """Resolve a call site to a target function and visit it.

        Returns the target node ID, or None if unresolvable / external.
        """
        if call.attr is None:
            # Simple call: foo()
            if call.name in imports:
                imp = imports[call.name]
                if imp.original_name is not None:
                    return self.visit_function(
                        imp.abs_path, imp.original_name, depth + 1
                    )
            if call.name in local_funcs:
                return self.visit_function(caller_file, call.name, depth + 1)
        else:
            # Attribute call: module.foo()
            if call.name in imports:
                imp = imports[call.name]
                if imp.original_name is None:
                    # Module-level import: import module → module.func()
                    return self.visit_function(imp.abs_path, call.attr, depth + 1)
        return None


class _ImportInfo:
    """Tracks where an imported name comes from."""

    __slots__ = ("abs_path", "original_name")

    def __init__(self, abs_path: str, original_name: str | None) -> None:
        self.abs_path = abs_path
        self.original_name = original_name


class _CallSite:
    """A function call found in the AST."""

    __slots__ = ("name", "attr", "line")

    def __init__(self, name: str, attr: str | None, line: int) -> None:
        self.name = name
        self.attr = attr
        self.line = line
