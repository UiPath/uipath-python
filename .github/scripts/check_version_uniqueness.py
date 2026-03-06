#!/usr/bin/env python3
"""Check that changed package versions don't already exist on PyPI.

Compares each changed package's version against the base branch.
If the version was bumped and that version already exists on PyPI,
the check fails — the developer must pick a new version.

This prevents the race condition where two PRs bump to the same version.
Branch protection ("require up to date") ensures this re-runs after rebase.
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
    """Check if a specific version of a package exists on PyPI.

    Returns:
        True if the version exists on PyPI.
        False if it does not (404).
        None if we couldn't determine (network error, non-404 HTTP error).
    """
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
        return None
    except Exception as e:
        print(
            f"  Warning: Could not reach PyPI for {package_name}=={version}: {e}",
            file=sys.stderr,
        )
        return None


def get_package_version(package_dir: str) -> tuple[str, str] | None:
    """Read package name and version from pyproject.toml."""
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


def get_base_version(package_dir: str) -> str | None:
    """Get the package version from the base branch (origin/main)."""
    pyproject_path = f"packages/{package_dir}/pyproject.toml"
    try:
        result = subprocess.run(
            ["git", "show", f"origin/main:{pyproject_path}"],
            capture_output=True,
            text=True,
            check=True,
        )
        data = tomllib.loads(result.stdout)
        return data.get("project", {}).get("version")
    except (subprocess.CalledProcessError, Exception):
        # File doesn't exist on main (new package) or parse error
        return None


def get_changed_packages(base_sha: str, head_sha: str) -> list[str]:
    """Get packages that have changed between two commits."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", f"{base_sha}...{head_sha}"],
            capture_output=True,
            text=True,
            check=True,
        )
        changed_files = result.stdout.strip().split("\n")
        changed_packages = set()
        for file_path in changed_files:
            if file_path.startswith("packages/"):
                parts = file_path.split("/")
                if len(parts) >= 2:
                    package_name = parts[1]
                    if (Path("packages") / package_name / "pyproject.toml").exists():
                        changed_packages.add(package_name)
        return sorted(changed_packages)
    except subprocess.CalledProcessError as e:
        print(f"Error running git diff: {e}", file=sys.stderr)
        return []


def get_changed_packages_auto() -> list[str]:
    """Auto-detect changed packages using git diff against origin/main."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "origin/main...HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        changed_files = result.stdout.strip().split("\n")
        changed_packages = set()
        for file_path in changed_files:
            if file_path.startswith("packages/"):
                parts = file_path.split("/")
                if len(parts) >= 2:
                    package_name = parts[1]
                    if (Path("packages") / package_name / "pyproject.toml").exists():
                        changed_packages.add(package_name)
        return sorted(changed_packages)
    except (subprocess.CalledProcessError, Exception) as e:
        print(f"Warning: Could not auto-detect changes: {e}", file=sys.stderr)
        return []


def main() -> int:
    """Main entry point. Returns 0 on success, 1 if a version conflict is found."""
    base_sha = os.getenv("BASE_SHA", "")
    head_sha = os.getenv("HEAD_SHA", "")

    if base_sha and head_sha:
        changed = get_changed_packages(base_sha, head_sha)
    else:
        changed = get_changed_packages_auto()

    if not changed:
        print("No changed packages detected — skipping version check.")
        return 0

    print(f"Checking version uniqueness for {len(changed)} changed package(s)...")

    conflicts = []
    for pkg_dir in changed:
        info = get_package_version(pkg_dir)
        if not info:
            continue

        name, version = info
        base_version = get_base_version(pkg_dir)

        if base_version == version:
            print(f"  {name}: version {version} unchanged — skipping")
            continue

        print(f"  {name}: version changed {base_version} → {version}")

        exists = version_exists_on_pypi(name, version)
        if exists is True:
            print(f"  ERROR: {name}=={version} already exists on PyPI!")
            conflicts.append(f"{name}=={version}")
        elif exists is False:
            print(f"  OK: {name}=={version} is available")
        else:
            print(f"  WARNING: Could not verify {name}=={version} — skipping check")

    if conflicts:
        print(
            f"\nFAILED: {len(conflicts)} package version(s) already exist on PyPI:",
            file=sys.stderr,
        )
        for c in conflicts:
            print(f"  - {c}", file=sys.stderr)
        print(
            "\nPlease bump the version(s) in the respective pyproject.toml file(s).",
            file=sys.stderr,
        )
        return 1

    print("\nAll version checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
