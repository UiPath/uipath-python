#!/usr/bin/env python3
"""Ensure min required versions are updated when co-modifying dependent packages.

When a PR modifies two packages where one depends on the other (e.g.
uipath-platform depends on uipath-core), the minimum required version of
the dependency must match the dependency's current version.

Example: if uipath-core is at version 0.5.7 and both uipath-core and
uipath-platform are modified, then uipath-platform's dependency on
uipath-core must specify >=0.5.7 (not an older minimum).
"""

import os
import re
import subprocess
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]

PACKAGES_DIR = Path("packages")


def get_changed_packages() -> set[str]:
    """Return set of package directory names that have source changes."""
    base_sha = os.getenv("BASE_SHA", "")
    head_sha = os.getenv("HEAD_SHA", "")
    diff_spec = (
        f"{base_sha}...{head_sha}" if base_sha and head_sha else "origin/main...HEAD"
    )

    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", diff_spec],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"Error running git diff: {e}", file=sys.stderr)
        return set()

    changed: set[str] = set()
    for file_path in result.stdout.strip().split("\n"):
        if file_path.startswith("packages/"):
            parts = file_path.split("/")
            if len(parts) >= 2:
                pkg_dir = parts[1]
                if (PACKAGES_DIR / pkg_dir / "pyproject.toml").exists():
                    changed.add(pkg_dir)
    return changed


def read_pyproject(pkg_dir: str) -> dict | None:
    """Read and parse a package's pyproject.toml."""
    pyproject = PACKAGES_DIR / pkg_dir / "pyproject.toml"
    if not pyproject.exists():
        return None
    with open(pyproject, "rb") as f:
        return tomllib.load(f)


def get_version(pyproject: dict) -> str | None:
    """Extract the version from parsed pyproject data."""
    return pyproject.get("project", {}).get("version")


def get_name(pyproject: dict) -> str | None:
    """Extract the package name from parsed pyproject data."""
    return pyproject.get("project", {}).get("name")


def get_dependencies(pyproject: dict) -> list[str]:
    """Extract the dependencies list from parsed pyproject data."""
    return pyproject.get("project", {}).get("dependencies", [])


def parse_min_version(dep_spec: str, dep_name: str) -> str | None:
    """Extract the minimum version from a dependency specifier.

    Looks for >=X.Y.Z pattern in a dependency string like
    "uipath-core>=0.5.4, <0.6.0".
    """
    pattern = rf"^{re.escape(dep_name)}>=([^\s,]+)"
    match = re.match(pattern, dep_spec.strip())
    if match:
        return match.group(1)
    return None


def check_min_versions(changed_packages: set[str]) -> list[str]:
    """Check that min required versions are up to date for changed packages.

    Returns a list of error messages for any violations found.
    """
    errors: list[str] = []

    # Build a map of package name -> (dir_name, current_version)
    pkg_info: dict[str, tuple[str, str]] = {}
    for pkg_dir in sorted(PACKAGES_DIR.iterdir()):
        if not pkg_dir.is_dir():
            continue
        pyproject = read_pyproject(pkg_dir.name)
        if pyproject is None:
            continue
        name = get_name(pyproject)
        version = get_version(pyproject)
        if name and version:
            pkg_info[name] = (pkg_dir.name, version)

    # For each changed package, check its dependencies against other changed packages
    for pkg_dir in sorted(changed_packages):
        pyproject = read_pyproject(pkg_dir)
        if pyproject is None:
            continue

        pkg_name = get_name(pyproject)
        if not pkg_name:
            continue

        for dep_spec in get_dependencies(pyproject):
            for dep_name, (dep_dir, dep_version) in pkg_info.items():
                if dep_dir not in changed_packages:
                    continue

                min_ver = parse_min_version(dep_spec, dep_name)
                if min_ver is None:
                    continue

                if min_ver != dep_version:
                    errors.append(
                        f"{pkg_name} requires {dep_name}>={min_ver}, "
                        f"but {dep_name} is at version {dep_version}. "
                        f"Update the minimum version in "
                        f"packages/{pkg_dir}/pyproject.toml to "
                        f"{dep_name}>={dep_version}"
                    )

    return errors


def main() -> int:
    """Run the min required version check."""
    changed = get_changed_packages()
    if not changed:
        print("No changed packages detected.")
        return 0

    print(f"Changed packages: {', '.join(sorted(changed))}")
    errors = check_min_versions(changed)

    if errors:
        print("\nMin required version check FAILED:", file=sys.stderr)
        for err in errors:
            print(f"  FAIL: {err}", file=sys.stderr)
        return 1

    print("Min required version check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
