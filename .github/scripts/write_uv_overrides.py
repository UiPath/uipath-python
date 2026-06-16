"""Write a uv override file forcing the locally built uipath wheels.

Cross-test workflows build uipath wheels from the PR and run them against
downstream repos (uipath-langchain-python, uipath-integrations-python,
uipath-runtime-python). Those downstreams cap the uipath* version (e.g.
``uipath<2.11.0``), so a backward-compatible minor bump would fail resolution
purely on the cap. uv ``override-dependencies`` ignore the declared version
specifier, so pointing them at the local wheels lets the cross-test exercise the
real new code regardless of the cap.

The script is layout-agnostic: it overrides whatever ``uipath*`` wheels exist
under ``$GITHUB_WORKSPACE/wheels`` (recursively), so it works for the
three-wheel layout (``wheels/<pkg>/dist/*.whl``) and the single-wheel runtime
layout (``wheels/*.whl``) alike.

The resulting override file path is appended to ``GITHUB_ENV`` as ``UV_OVERRIDE``
so every subsequent ``uv`` invocation in the job honors it.
"""

import glob
import os
import pathlib


def main() -> None:
    wheels = pathlib.Path(os.environ.get("GITHUB_WORKSPACE", ".")).resolve() / "wheels"

    lines = []
    for whl in sorted(glob.glob(str(wheels / "**" / "*.whl"), recursive=True)):
        # Wheel filename is ``{distribution}-{version}-...whl`` where the
        # distribution escapes hyphens to underscores (uipath_core -> uipath-core).
        dist = pathlib.Path(whl).name.split("-", 1)[0].replace("_", "-")
        if not dist.startswith("uipath"):
            continue
        lines.append(f"{dist} @ {pathlib.Path(whl).resolve().as_uri()}")

    if not lines:
        raise SystemExit(f"no uipath wheels found under {wheels}")

    out = wheels / "overrides.txt"
    out.write_text("\n".join(lines) + "\n")

    with open(os.environ["GITHUB_ENV"], "a") as fh:
        fh.write(f"UV_OVERRIDE={out}\n")

    print("\n".join(lines))


if __name__ == "__main__":
    main()
