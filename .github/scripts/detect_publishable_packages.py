#!/usr/bin/env python3
"""Detect which packages need publishing to PyPI.

Compares local package versions against what's already on PyPI.
Only outputs packages whose local version doesn't exist on PyPI yet.
"""

import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]


def get_all_packages() -> list[dict[str, str]]:
    """Get all packages with their names and versions from pyproject.toml."""
    packages_dir = Path("packages")
    packages = []

    for item in sorted(packages_dir.iterdir()):
        pyproject = item / "pyproject.toml"
        if item.is_dir() and pyproject.exists():
            with open(pyproject, "rb") as f:
                data = tomllib.load(f)
            project = data.get("project", {})
            name = project.get("name")
            version = project.get("version")
            if name and version:
                packages.append(
                    {"directory": item.name, "name": name, "version": version}
                )

    return packages


def version_exists_on_pypi(package_name: str, version: str) -> bool:
    """Check if a specific version of a package exists on PyPI."""
    url = f"https://pypi.org/pypi/{package_name}/{version}/json"
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=10):
            return True
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False
        print(
            f"  Warning: PyPI returned HTTP {e.code} for {package_name}=={version}",
            file=sys.stderr,
        )
        return False
    except Exception as e:
        print(
            f"  Warning: Could not check PyPI for {package_name}=={version}: {e}",
            file=sys.stderr,
        )
        # If we can't reach PyPI, skip publishing to be safe
        return True


def main():
    """Main entry point."""
    all_packages = get_all_packages()
    publishable = []

    print(f"Checking {len(all_packages)} package(s) against PyPI...")

    for pkg in all_packages:
        name, version, directory = pkg["name"], pkg["version"], pkg["directory"]
        exists = version_exists_on_pypi(name, version)
        if exists:
            print(f"  {name}=={version} — already on PyPI, skipping")
        else:
            print(f"  {name}=={version} — new version, will publish")
            publishable.append(directory)

    # Output as JSON for GitHub Actions
    packages_json = json.dumps(publishable)
    print(f"\nPublishable packages JSON: {packages_json}")

    github_output = os.getenv("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"packages={packages_json}\n")
            f.write(f"count={len(publishable)}\n")


if __name__ == "__main__":
    main()
