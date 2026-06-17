# SETUP.MD

This file documents how to provision a clean development environment for the three packages in this repo (`uipath-core`, `uipath-platform`, `uipath`), run the build, execute the tests, and validate a sample code change end-to-end. It is intended both as a quick reference for human contributors and as a structured guide for automated environment-setup tooling.

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) 0.5+

### Supported platforms

`uv` is shell- and OS-agnostic, so the commands below run unchanged on every supported platform:

- [x] Linux
- [x] Windows
- [x] macOS

## Environment Variables

None required for environment setup, build, or unit tests. The suites under the `Test` section run fully offline and require no external authentication.

> **All commands below must be run from the repository root.** The `uv --directory packages/<name>` invocations resolve each subpackage relative to the current working directory. The first line of `## Setup` enforces this by `cd`-ing to the git root.

## Setup

```bash
cd "$(git rev-parse --show-toplevel)"
python3 -m pip install --upgrade uv

# Sync all three packages (dependency order: core → platform → main)
uv --directory packages/uipath-core sync --all-extras
uv --directory packages/uipath-platform sync --all-extras
uv --directory packages/uipath sync --all-extras
```

## Verify Setup

```bash
uv --version
uv --directory packages/uipath-core run python --version
uv --directory packages/uipath-core run python -c "import uipath.core; print('uipath-core ok')"
uv --directory packages/uipath-platform run python -c "import uipath.platform; print('uipath-platform ok')"
uv --directory packages/uipath run python -c "import uipath; print('uipath ok')"
```

## Build

N/A

## Test

```bash
uv --directory packages/uipath-core run pytest
uv --directory packages/uipath-platform run pytest
uv --directory packages/uipath run pytest
```

> Note: `uipath-platform`'s `pyproject.toml` already excludes its E2E tests via `addopts = "... -m 'not e2e'"`. `uipath-core` and `uipath` do not register an `e2e` marker.

## Sample Code Change

### The change

Add a new `size` property to `SpanRegistry` in `packages/uipath-core/src/uipath/core/tracing/span_utils.py`, immediately after the `clear` method and before the `# Global span registry instance` comment:

```python
@property
def size(self) -> int:
    """Return the number of currently registered spans."""
    return len(self._spans)
```

Then create `packages/uipath-core/tests/tracing/test_span_registry_size.py` with two pytest tests:

```python
from unittest.mock import MagicMock

from uipath.core.tracing.span_utils import SpanRegistry


def _make_span(span_id: int) -> MagicMock:
    span = MagicMock()
    span.get_span_context.return_value.span_id = span_id
    span.parent = None  # registered as a root span (no parent)
    return span


def test_size_empty_registry() -> None:
    registry = SpanRegistry()
    assert registry.size == 0


def test_size_after_registrations() -> None:
    registry = SpanRegistry()
    registry.register_span(_make_span(1))
    registry.register_span(_make_span(2))
    assert registry.size == 2
```

### Verification

```bash
uv --directory packages/uipath-core run pytest tests/tracing/test_span_registry_size.py -v
```

## Test with a real UiPath Coded Agent

> This section is for human contributors who want to validate changes end-to-end against the real cloud platform. It is **not executed by the Agentic Inner Loop validation pipeline** — that pipeline only runs the sections above (Setup → Verify → Build → Test → Sample Code Change).

The unit tests above are necessary but not sufficient — they don't exercise the package end-to-end through a real agent. The flow below validates changes against a live runtime:

1. Apply the code changes locally.
2. Run the unit tests (see the `Sample Code Change` section above).
3. Scaffold a coded UiPath agent that exercises the changed code path.
4. In the downstream project's `pyproject.toml`, add this local library as an editable dependency (substitute `uipath`, `uipath-platform`, or `uipath-core` depending on which package you changed):

   ```toml
   [tool.uv.sources]
   uipath = { path = "../path/to/uipath-python/packages/uipath", editable = true }
   ```

5. Exercise the new behavior end-to-end:

   ```bash
   uv run uipath run <agent-name> --input '{...}'
   ```

6. (Optional) Open a PR and apply the `build:dev` label — this publishes the development version to Test PyPI.
7. The PR description is updated automatically with instructions for pointing the downstream agent at the Test PyPI dev version.
8. Validate the new behavior against the real platform — use either or both of the deploy targets below (Studio Web and Orchestrator are not mutually exclusive):
   - **Studio Web**: export the `UIPATH_PROJECT_ID` environment variable pointing to an existing Coded Agent project in your solution, then run [`uipath push`](https://uipath.github.io/uipath-python/cli/#push) to push the dev version to that project. Open it in Studio Web and exercise the changed code path.
   - **Orchestrator**: run [`uipath deploy`](https://uipath.github.io/uipath-python/cli/#deploy) to deploy the dev version as a package, then start a job in Orchestrator and exercise the changed code path.
9. Once validation is done, close the dev PR — these PRs are not meant to be merged; their only purpose was to publish a Test PyPI build for end-to-end validation.
