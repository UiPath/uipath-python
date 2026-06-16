"""Write a uv override file forcing the locally built uipath wheels.

Cross-test workflows build uipath-core/uipath-platform/uipath wheels from the PR
and run them against downstream repos (uipath-langchain-python,
uipath-integrations-python). Those downstreams cap the uipath version (e.g.
``uipath<2.11.0``), so a backward-compatible minor bump would fail resolution
purely on the cap. uv ``override-dependencies`` bypass the declared version
specifier, so pointing them at the local wheels lets the cross-test exercise the
real new code regardless of the cap.

The wheels are resolved relative to ``GITHUB_WORKSPACE`` (where the
``download-artifact`` step places them) rather than the current directory, so the
script is robust to a step- or job-level ``working-directory``.

The resulting override file path is appended to ``GITHUB_ENV`` as ``UV_OVERRIDE``
so every subsequent ``uv`` invocation in the job honors it.
"""

import glob
import os
import pathlib


def main() -> None:
    workspace = pathlib.Path(os.environ.get("GITHUB_WORKSPACE", ".")).resolve()
    wheels = workspace / "wheels"

    lines = []
    for name in ("uipath", "uipath-core", "uipath-platform"):
        matches = glob.glob(str(wheels / name / "dist" / "*.whl"))
        if not matches:
            raise SystemExit(f"no wheel found for {name} under {wheels / name / 'dist'}")
        lines.append(f"{name} @ {pathlib.Path(matches[0]).resolve().as_uri()}")

    out = wheels / "overrides.txt"
    out.write_text("\n".join(lines) + "\n")

    with open(os.environ["GITHUB_ENV"], "a") as fh:
        fh.write(f"UV_OVERRIDE={out}\n")

    print("\n".join(lines))


if __name__ == "__main__":
    main()
