#!/usr/bin/env python3
"""Wait for a package version to become available on PyPI.

Usage: python wait_for_pypi.py <package-directory-name>

Reads the package name and version from packages/<dir>/pyproject.toml,
then polls PyPI until the version appears or a timeout is reached.
"""

import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]

MAX_WAIT = 300  # 5 minutes
POLL_INTERVAL = 15  # seconds


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
        print(f"  Warning: PyPI returned HTTP {e.code}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"  Warning: Could not reach PyPI: {e}", file=sys.stderr)
        return False


def main() -> int:
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <package-directory>", file=sys.stderr)
        return 1

    directory = sys.argv[1]
    pyproject = Path("packages") / directory / "pyproject.toml"

    if not pyproject.exists():
        print(f"ERROR: {pyproject} not found", file=sys.stderr)
        return 1

    with open(pyproject, "rb") as f:
        data = tomllib.load(f)

    name = data["project"]["name"]
    version = data["project"]["version"]

    print(f"Waiting for {name}=={version} to appear on PyPI...")
    elapsed = 0
    while elapsed < MAX_WAIT:
        if version_exists_on_pypi(name, version):
            print(f"{name}=={version} is now available on PyPI.")
            return 0
        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL
        print(f"  Still waiting... ({elapsed}s/{MAX_WAIT}s)")

    print(
        f"ERROR: {name}=={version} did not appear on PyPI within {MAX_WAIT}s",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
