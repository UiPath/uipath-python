"""Test that all modules can be imported without circular dependency errors.

This test automatically discovers all modules in uipath_langchain and tests each
one with isolated imports to catch runtime circular imports.
"""

import importlib
import pkgutil
import sys
from typing import Iterator

import pytest


def discover_all_modules(package_name: str) -> Iterator[str]:
    """Discover all importable modules in a package recursively.

    Args:
        package_name: The top-level package name (e.g., 'uipath_langchain')

    Yields:
        Fully qualified module names (e.g., 'uipath_langchain.agent.tools')
    """
    try:
        package = importlib.import_module(package_name)
        package_path = package.__path__
    except ImportError:
        return

    # Recursively walk through all modules
    for _importer, modname, _ispkg in pkgutil.walk_packages(
        path=package_path, prefix=f"{package_name}.", onerror=lambda x: None
    ):
        yield modname


def get_all_module_imports() -> list[str]:
    """Get all modules to test.

    Returns:
        List of module names to test
    """
    modules = list(discover_all_modules("uipath"))

    # Filter out optional dependency modules that won't be installed
    exclude: set[str] = set()
    return [m for m in modules if m not in exclude]


@pytest.mark.parametrize("module_name", get_all_module_imports())
def test_module_imports_with_isolation(module_name: str) -> None:
    """Test that a module can be imported in isolation.

    Clears all uipath_langchain modules from sys.modules before importing to
    catch circular imports that would be masked by module caching.

    Args:
        module_name: The fully qualified module name to test

    Raises:
        pytest.fail: If the module cannot be imported due to circular dependency
    """
    # Clear all uipath_langchain modules from sys.modules to force fresh import
    to_remove = [key for key in sys.modules.keys() if "uipath" in key]
    for key in to_remove:
        del sys.modules[key]

    # Now try importing the module in isolation
    try:
        importlib.import_module(module_name)
    except ImportError as e:
        if "circular import" in str(e).lower():
            pytest.fail(
                f"Circular import in {module_name}:\n{e}",
                pytrace=False,
            )
        # Other import errors (missing dependencies, syntax errors, etc)
        pytest.fail(
            f"Failed to import {module_name}:\n{e}",
            pytrace=False,
        )
