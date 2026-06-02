#!/usr/bin/env python3
"""Enforce minimum-version bumps between co-changed internal packages.

The monorepo ships several packages that depend on one another
(``uipath`` -> ``uipath-platform`` -> ``uipath-core``). When a PR changes
the *source* of a dependency package (say ``uipath-core``) **and** the
source of one of its dependents (say ``uipath``), the dependent is almost
certainly relying on the new behaviour. If the dependent does not also
raise the lower bound of its requirement on the dependency, then anyone who
installs the dependent on its own can resolve an older dependency that
predates the new behaviour — a silent runtime break.

This check fails such a PR. For every pair of co-changed (dependency,
dependent) packages it requires the dependent's lower-bound constraint on
the dependency (the ``>=`` part of e.g. ``uipath-core>=0.5.8, <0.6.0``) to
be at least the dependency's new version declared in this PR.

The internal dependency graph is discovered from the pyproject files, so no
hard-coded list needs maintaining as packages are added.
"""

import re
import sys
from pathlib import Path
from typing import TypedDict

from check_version_uniqueness import get_changed_packages

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]

PACKAGES_DIR = Path("packages")


class PackageInfo(TypedDict):
    """Resolved metadata for a single monorepo package."""

    dir: str
    name: str
    version: str
    dependencies: list[str]


def normalize_name(name: str) -> str:
    """Normalize a PyPI project name (PEP 503): case-insensitive, -/_/.
    treated as equivalent."""
    return re.sub(r"[-_.]+", "-", name).lower()


def version_key(version: str) -> tuple[int, ...]:
    """Numeric sort key so ``0.5.17`` > ``0.5.8`` (``0.5.18rc1`` -> ``(0, 5, 18)``)."""
    parts: list[int] = []
    for component in version.split("."):
        digits = ""
        for ch in component:
            if ch.isdigit():
                digits += ch
            else:
                break
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def parse_requirement(requirement: str) -> tuple[str | None, str | None]:
    """Extract (normalized name, lower-bound version) from a requirement string.

    Returns the lower bound found in a ``>=`` clause, or ``None`` if there is
    no ``>=`` constraint. The name is ``None`` if the string is unparseable.
    """
    name_match = re.match(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)", requirement)
    if not name_match:
        return None, None
    name = normalize_name(name_match.group(1))

    lower: str | None = None
    lower_match = re.search(r">=\s*([0-9][0-9A-Za-z._-]*)", requirement)
    if lower_match:
        lower = lower_match.group(1)
    return name, lower


def load_package(package_dir: str) -> PackageInfo | None:
    """Read a package's name, version and dependency list from pyproject.toml."""
    pyproject = PACKAGES_DIR / package_dir / "pyproject.toml"
    if not pyproject.exists():
        return None
    with open(pyproject, "rb") as f:
        data = tomllib.load(f)
    project = data.get("project", {})
    name = project.get("name")
    version = project.get("version")
    if not name or not version:
        return None
    return PackageInfo(
        dir=package_dir,
        name=name,
        version=version,
        dependencies=list(project.get("dependencies", [])),
    )


def get_all_packages() -> dict[str, PackageInfo]:
    """Map package directory name -> package info for every package."""
    packages: dict[str, PackageInfo] = {}
    if not PACKAGES_DIR.is_dir():
        return packages
    for item in sorted(PACKAGES_DIR.iterdir()):
        if item.is_dir() and (item / "pyproject.toml").exists():
            info = load_package(item.name)
            if info:
                packages[item.name] = info
    return packages


def check(packages: dict[str, PackageInfo], changed: set[str]) -> list[str]:
    """Return a list of violation messages (empty when the PR is compliant)."""
    name_to_dir: dict[str, str] = {
        normalize_name(info["name"]): pkg_dir for pkg_dir, info in packages.items()
    }

    violations: list[str] = []
    for dependent_dir in sorted(changed):
        dependent = packages.get(dependent_dir)
        if not dependent:
            continue

        for requirement in dependent["dependencies"]:
            dep_name, lower = parse_requirement(requirement)
            if dep_name is None:
                continue

            dep_dir = name_to_dir.get(dep_name)
            # Only internal packages that *also* changed in this PR are in scope.
            if dep_dir is None or dep_dir == dependent_dir or dep_dir not in changed:
                continue

            dep_version = packages[dep_dir]["version"]
            dep_display = packages[dep_dir]["name"]

            if lower is None:
                violations.append(
                    f"{dependent['name']} requires '{requirement}' but has no '>=' lower bound on "
                    f"{dep_display}; pin it to >={dep_version} (both packages changed in this PR)."
                )
            elif version_key(lower) < version_key(dep_version):
                violations.append(
                    f"{dependent['name']} pins {dep_display}>={lower}, but {dep_display} was bumped to "
                    f"{dep_version} in this PR. Raise the minimum to >={dep_version}."
                )
            else:
                print(f"OK: {dependent['name']} requires {dep_display}>={lower} (>= new {dep_version})")

    return violations


def main() -> int:
    packages = get_all_packages()
    if not packages:
        print("No packages found.")
        return 0

    changed = set(get_changed_packages())
    if not changed:
        print("No source changes to internal packages detected.")
        return 0

    print(f"Changed packages: {', '.join(sorted(changed))}")

    violations = check(packages, changed)
    if violations:
        print("\nDependency version bump check FAILED:\n", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        print(
            "\nWhen you change an internal package and a dependent of it in the same PR, "
            "the dependent must require the dependency's new version so a standalone install "
            "cannot resolve an older, incompatible release.",
            file=sys.stderr,
        )
        return 1

    print("\nAll co-changed internal dependencies have an up-to-date minimum version.")
    return 0


if __name__ == "__main__":
    sys.exit(main())