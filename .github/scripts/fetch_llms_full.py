#!/usr/bin/env python3
"""Refresh the bundled offline `llms-full.txt` from the live docs site.

Driven by `.github/workflows/refresh-llms-full.yml` on a daily schedule.
The workflow opens a PR if the file changed. On network failure, the
existing bundled copy is kept.
"""

import sys
import urllib.error
import urllib.request
from pathlib import Path

URL = "https://uipath.github.io/uipath-python/llms-full.txt"
REPO_ROOT = Path(__file__).resolve().parents[2]
DEST = REPO_ROOT / "packages" / "uipath" / "src" / "uipath" / "_resources" / "llms-full.txt"


def main() -> int:
    """Download the latest llms-full.txt or fall back to the cached copy."""
    try:
        with urllib.request.urlopen(URL, timeout=30) as response:
            data = response.read()
    except (urllib.error.URLError, TimeoutError) as e:
        if DEST.exists():
            print(f"warning: could not fetch {URL} ({e}); keeping existing {DEST.name}")
            return 0
        print(f"error: could not fetch {URL} ({e}) and no cached copy exists")
        return 1

    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_bytes(data)
    print(f"updated {DEST} ({len(data)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
