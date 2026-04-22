#!/usr/bin/env python3
"""Ensure every changed package has a version not yet published to PyPI.

For each package with file changes in the PR, we read its version from
pyproject.toml and check whether that exact version exists on PyPI.
If it does, the check fails — the developer must bump the version.

This catches two scenarios:
  1. Developer changed code but forgot to bump the version.
  2. Two PRs raced to the same version — after rebase the first PR's
     version is already on PyPI, so this check forces the second PR
     to pick a new one.
"""

import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]


def version_exists_on_pypi(package_name: str, version: str) -> bool | None:
    url = f"https://pypi.org/pypi/{package_name}/{version}/json"
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=10):
            return True
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False
        print(f"Warning: PyPI returned HTTP {e.code} for {package_name}=={version}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Warning: Could not reach PyPI for {package_name}=={version}: {e}", file=sys.stderr)
        return None


def get_package_info(package_dir: str) -> tuple[str, str] | None:
    pyproject = Path("packages") / package_dir / "pyproject.toml"
    if not pyproject.exists():
        return None
    with open(pyproject, "rb") as f:
        data = tomllib.load(f)
    project = data.get("project", {})
    name = project.get("name")
    version = project.get("version")
    if name and version:
        return name, version
    return None


def get_changed_packages() -> list[str]:
    base_sha = os.getenv("BASE_SHA", "")
    head_sha = os.getenv("HEAD_SHA", "")
    diff_spec = f"{base_sha}...{head_sha}" if base_sha and head_sha else "origin/main...HEAD"

    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", diff_spec],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"Error running git diff: {e}", file=sys.stderr)
        return []

    changed = set()
    for file_path in result.stdout.strip().split("\n"):
        if file_path.startswith("packages/"):
            parts = file_path.split("/")
            if len(parts) >= 3 and parts[2] == "src" and (Path("packages") / parts[1] / "pyproject.toml").exists():
                changed.add(parts[1])
    return sorted(changed)


def main() -> int:
    changed = get_changed_packages()
    if not changed:
        print("No changed packages detected.")
        return 0

    conflicts = []
    failures = []
    for pkg_dir in changed:
        info = get_package_info(pkg_dir)
        if not info:
            continue

        name, version = info
        exists = version_exists_on_pypi(name, version)

        if exists is True:
            print(f"FAIL: {name}=={version} already exists on PyPI")
            conflicts.append(f"{name}=={version}")
        elif exists is False:
            print(f"OK: {name}=={version} is available")
        else:
            print(f"FAIL: could not verify {name}=={version}")
            failures.append(f"{name}=={version}")

    success = len(conflicts) + len(failures) == 0
    if not success:
        if conflicts:
            print(f"\nPlease bump the version in pyproject.toml for: {', '.join(conflicts)}", file=sys.stderr)
        if failures:
            print(f"\nError while trying to check the following packages on pypi index: {', '.join(failures)}. Please retry.", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
