#!/usr/bin/env python3
"""Detect which packages have changed in a PR or push to main.

Includes dependency-aware propagation: when a package changes, all
downstream dependents are also included in the test list.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

# Internal dependency graph: package -> packages that depend on it.
# When a package changes, its dependents' tests also run.
# Add new entries here as packages are added to the monorepo.
# External dependents (uipath-langchain, uipath-runtime, etc.) are
# handled separately via labeler.yml auto-labels.
DEPENDENTS: dict[str, list[str]] = {
    "uipath-core": ["uipath-platform", "uipath"],
    "uipath-platform": ["uipath"],
}


def expand_with_dependents(changed: list[str], all_packages: list[str]) -> list[str]:
    """Expand changed package list to include downstream dependents."""
    expanded = set(changed)
    for pkg in changed:
        for dep in DEPENDENTS.get(pkg, []):
            if dep in all_packages:
                expanded.add(dep)
    return sorted(expanded)


def get_all_packages() -> list[str]:
    """Get all packages in the monorepo."""
    packages_dir = Path("packages")
    packages = []

    for item in packages_dir.iterdir():
        if item.is_dir() and (item / "pyproject.toml").exists():
            packages.append(item.name)

    return sorted(packages)


def get_changed_packages(base_sha: str, head_sha: str) -> list[str]:
    """Get packages that have changed between two commits."""
    try:
        # Get changed files
        result = subprocess.run(
            ["git", "diff", "--name-only", f"{base_sha}...{head_sha}"],
            capture_output=True,
            text=True,
            check=True,
        )

        changed_files = result.stdout.strip().split("\n")

        # Extract package names from paths like "packages/uipath-llamaindex/..."
        changed_packages = set()
        for file_path in changed_files:
            if file_path.startswith("packages/"):
                parts = file_path.split("/")
                if len(parts) >= 2:
                    package_name = parts[1]
                    # Verify it's a real package
                    if (Path("packages") / package_name / "pyproject.toml").exists():
                        changed_packages.add(package_name)

        return sorted(changed_packages)

    except subprocess.CalledProcessError as e:
        print(f"Error running git diff: {e}", file=sys.stderr)
        return []


def get_changed_packages_auto() -> list[str]:
    """Auto-detect changed packages using git."""
    try:
        # Try to detect changes against origin/main
        result = subprocess.run(
            ["git", "diff", "--name-only", "origin/main...HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )

        changed_files = result.stdout.strip().split("\n")

        # Extract package names
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


def main():
    """Main entry point."""
    event_name = os.getenv("GITHUB_EVENT_NAME", "")
    base_sha = os.getenv("BASE_SHA", "")
    head_sha = os.getenv("HEAD_SHA", "")

    all_packages = get_all_packages()

    # If we have explicit SHAs (from PR or push), detect changed packages
    if base_sha and head_sha:
        packages = get_changed_packages(base_sha, head_sha)
        event_type = "pull request" if event_name == "pull_request" else "push"
        print(f"{event_type.capitalize()} - detected {len(packages)} directly changed package(s):")
        for pkg in packages:
            print(f"  - {pkg}")

    # workflow_call or missing context - try auto-detection
    else:
        print(f"Event: {event_name or 'workflow_call'} - attempting auto-detection")
        packages = get_changed_packages_auto()

        if packages:
            print(f"Auto-detected {len(packages)} directly changed package(s):")
            for pkg in packages:
                print(f"  - {pkg}")
        else:
            # Fallback: test all packages
            print("Could not detect changes - testing all packages")
            packages = all_packages
            for pkg in packages:
                print(f"  - {pkg}")

    # Expand with downstream dependents
    expanded = expand_with_dependents(packages, all_packages)
    added = sorted(set(expanded) - set(packages))
    if added:
        print(f"\nAdded {len(added)} dependent package(s):")
        for pkg in added:
            print(f"  - {pkg}")
    packages = expanded

    # Output as JSON for GitHub Actions
    packages_json = json.dumps(packages)
    print(f"\nPackages JSON: {packages_json}")

    # Write to GitHub output
    github_output = os.getenv("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"packages={packages_json}\n")
            f.write(f"count={len(packages)}\n")


if __name__ == "__main__":
    main()
