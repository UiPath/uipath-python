#!/usr/bin/env python3
"""Custom linter to check for httpx.Client() usage.

This script checks for direct usage of httpx.Client() without using the
get_httpx_client_kwargs() function, which is required for proper SSL
and proxy configuration in the UiPath Python SDK.
"""

import ast
import sys
from pathlib import Path
from typing import List, NamedTuple


class LintViolation(NamedTuple):
    """Represents a linting violation."""

    filename: str
    line: int
    column: int
    message: str
    rule_code: str


class HttpxClientChecker(ast.NodeVisitor):
    """AST visitor to check for httpx.Client() usage violations."""

    def __init__(self, filename: str):
        """Initialize the checker with a filename.

        Args:
            filename: The path to the file being checked.
        """
        self.filename = filename
        self.violations: List[LintViolation] = []
        self.has_httpx_import = False
        self.has_get_httpx_client_kwargs_import = False
        # Track variables that contain get_httpx_client_kwargs
        self.variables_with_httpx_kwargs: set[str] = set()

    def visit_Import(self, node: ast.Import) -> None:
        """Check for httpx imports."""
        for alias in node.names:
            if alias.name == "httpx":
                self.has_httpx_import = True
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Check for imports from httpx or get_httpx_client_kwargs."""
        if node.module == "httpx":
            self.has_httpx_import = True
        elif node.module and "get_httpx_client_kwargs" in [
            alias.name for alias in (node.names or [])
        ]:
            self.has_get_httpx_client_kwargs_import = True
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        """Track variable assignments that use get_httpx_client_kwargs."""
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            var_name = node.targets[0].id
            if self._assignment_uses_get_httpx_client_kwargs(node.value):
                self.variables_with_httpx_kwargs.add(var_name)
        self.generic_visit(node)

    def _assignment_uses_get_httpx_client_kwargs(self, value_node: ast.AST) -> bool:
        """Check if an assignment value uses get_httpx_client_kwargs."""
        if isinstance(value_node, ast.Call):
            # Direct call: var = get_httpx_client_kwargs()
            if isinstance(value_node.func, ast.Name):
                if value_node.func.id == "get_httpx_client_kwargs":
                    return True
            elif isinstance(value_node.func, ast.Attribute):
                if value_node.func.attr == "get_httpx_client_kwargs":
                    return True
        elif isinstance(value_node, ast.Dict):
            # Dictionary that spreads get_httpx_client_kwargs: {..., **get_httpx_client_kwargs()}
            for key in value_node.keys:
                if key is None:  # This is a **kwargs expansion
                    # Find corresponding value
                    idx = value_node.keys.index(key)
                    if idx < len(value_node.values):
                        spread_value = value_node.values[idx]
                        if isinstance(spread_value, ast.Call):
                            if isinstance(spread_value.func, ast.Name):
                                if spread_value.func.id == "get_httpx_client_kwargs":
                                    return True
                            elif isinstance(spread_value.func, ast.Attribute):
                                if spread_value.func.attr == "get_httpx_client_kwargs":
                                    return True
                        elif isinstance(spread_value, ast.Name):
                            # Spreading another variable that might contain httpx kwargs
                            if spread_value.id in self.variables_with_httpx_kwargs:
                                return True
        return False

    def visit_Call(self, node: ast.Call) -> None:
        """Check for httpx.Client() and httpx.AsyncClient() calls."""
        if self._is_httpx_client_call(node):
            # Check if this is a proper usage with get_httpx_client_kwargs
            if not self._is_using_get_httpx_client_kwargs(node):
                client_type = self._get_client_type(node)
                violation = LintViolation(
                    filename=self.filename,
                    line=node.lineno,
                    column=node.col_offset,
                    message=f"Use **get_httpx_client_kwargs() with {client_type}() - should be: {client_type}(**get_httpx_client_kwargs())",
                    rule_code="UIPATH001",
                )
                self.violations.append(violation)

        self.generic_visit(node)

    def _is_httpx_client_call(self, node: ast.Call) -> bool:
        """Check if the call is httpx.Client() or httpx.AsyncClient()."""
        if isinstance(node.func, ast.Attribute):
            if (
                isinstance(node.func.value, ast.Name)
                and node.func.value.id == "httpx"
                and node.func.attr in ("Client", "AsyncClient")
            ):
                return True
        elif isinstance(node.func, ast.Name) and node.func.id in (
            "Client",
            "AsyncClient",
        ):
            # This could be a direct Client/AsyncClient import, check if httpx is imported
            return self.has_httpx_import
        return False

    def _get_client_type(self, node: ast.Call) -> str:
        """Get the client type name (Client or AsyncClient)."""
        if isinstance(node.func, ast.Attribute):
            return f"httpx.{node.func.attr}"
        elif isinstance(node.func, ast.Name):
            return node.func.id
        return "httpx.Client"

    def _is_using_get_httpx_client_kwargs(self, node: ast.Call) -> bool:
        """Check if the httpx.Client() call is using **get_httpx_client_kwargs()."""
        # Check if there are any **kwargs that use get_httpx_client_kwargs directly
        for keyword in node.keywords:
            if keyword.arg is None:  # This is a **kwargs expansion
                if isinstance(keyword.value, ast.Call):
                    if isinstance(keyword.value.func, ast.Name):
                        if keyword.value.func.id == "get_httpx_client_kwargs":
                            return True
                    elif isinstance(keyword.value.func, ast.Attribute):
                        if keyword.value.func.attr == "get_httpx_client_kwargs":
                            return True
                elif isinstance(keyword.value, ast.Name):
                    # Check if this variable might contain get_httpx_client_kwargs
                    # This handles cases like: **client_kwargs where client_kwargs was built from get_httpx_client_kwargs
                    var_name = keyword.value.id
                    if self._variable_contains_get_httpx_client_kwargs(var_name):
                        return True

        # Also check if it's the ONLY argument and it's **get_httpx_client_kwargs()
        # This handles cases like: httpx.Client(**get_httpx_client_kwargs())
        if len(node.args) == 0 and len(node.keywords) == 1:
            keyword = node.keywords[0]
            if keyword.arg is None and isinstance(keyword.value, ast.Call):
                if isinstance(keyword.value.func, ast.Name):
                    if keyword.value.func.id == "get_httpx_client_kwargs":
                        return True
                elif isinstance(keyword.value.func, ast.Attribute):
                    if keyword.value.func.attr == "get_httpx_client_kwargs":
                        return True

        return False

    def _variable_contains_get_httpx_client_kwargs(self, var_name: str) -> bool:
        """Check if a variable was built using get_httpx_client_kwargs()."""
        # Check if we've tracked this variable as containing httpx kwargs
        if var_name in self.variables_with_httpx_kwargs:
            return True

        # Fallback: Simple heuristic based on naming patterns
        # This handles cases where the variable assignment might be complex
        if "client_kwargs" in var_name.lower() or "httpx_kwargs" in var_name.lower():
            return True

        return False


def check_file(filepath: Path) -> List[LintViolation]:
    """Check a single Python file for httpx.Client() violations."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        tree = ast.parse(content, filename=str(filepath))
        checker = HttpxClientChecker(str(filepath))
        checker.visit(tree)
        return checker.violations

    except SyntaxError:
        # Skip files with syntax errors
        return []
    except Exception as e:
        print(f"Error checking {filepath}: {e}", file=sys.stderr)
        return []


def main():
    """Main function to run the linter."""
    if len(sys.argv) > 1:
        paths = [Path(p) for p in sys.argv[1:]]
    else:
        # Default to checking src and tests directories
        paths = [Path("src"), Path("tests")]

    all_violations = []

    for path in paths:
        if path.is_file() and path.suffix == ".py":
            violations = check_file(path)
            all_violations.extend(violations)
        elif path.is_dir():
            for py_file in path.rglob("*.py"):
                violations = check_file(py_file)
                all_violations.extend(violations)

    # Report violations
    if all_violations:
        for violation in all_violations:
            print(
                f"{violation.filename}:{violation.line}:{violation.column}: {violation.rule_code} {violation.message}"
            )
        sys.exit(1)
    else:
        print("No httpx.Client() violations found.")
        sys.exit(0)


if __name__ == "__main__":
    main()
