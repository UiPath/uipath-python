# SETUP.MD

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) 0.5+

### Supported platforms

This checklist controls the Agentic Inner Loop KPI pipeline targets (clean Linux VM). The repo's own GitHub Actions CI additionally tests on `windows-latest`, but that is not measured by this KPI.

- [x] Linux
- [ ] Windows
- [ ] macOS

## Environment Variables

### Standard (injected by pipeline)

None of the standard pipeline variables are required for environment setup, build, or unit tests.

### Project-specific

None. The unit-test suites under the `Test` section below run fully offline and require no external authentication.

## Setup

```bash
# Install uv if not already on PATH (no-op when pre-installed by the pipeline)
python3 -m pip install --upgrade uv

# Sync all three packages with dev dependencies (dependency order: core → platform → main)
uv --directory packages/uipath-core sync --all-extras
uv --directory packages/uipath-platform sync --all-extras
uv --directory packages/uipath sync --all-extras
```

## Verify Setup

```bash
python3 --version
uv --version
uv --directory packages/uipath-core run python -c "import uipath.core; print('uipath-core ok')"
uv --directory packages/uipath-platform run python -c "import uipath.platform; print('uipath-platform ok')"
uv --directory packages/uipath run python -c "import uipath; print('uipath ok')"
```

## Build

```bash
uv --directory packages/uipath-core build
uv --directory packages/uipath-platform build
uv --directory packages/uipath build
```

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
