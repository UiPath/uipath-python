# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is the **UiPath Python SDK** monorepo — a Python SDK and CLI for programmatic interaction with the UiPath Cloud Platform. It publishes three packages to PyPI: `uipath`, `uipath-core`, and `uipath-platform`.

## Monorepo Structure

The repo contains three packages under `packages/`, each with its own `pyproject.toml`, `src/`, and `tests/`:

- **`packages/uipath`** — The main SDK package. Contains the CLI (`uipath` command), agent framework, evaluation framework, tracing/telemetry, and function utilities. This is what users `uv pip install uipath`. Entry point: `src/uipath/_cli:cli`.
- **`packages/uipath-core`** — Core abstractions shared across packages: tracing, serialization, events, feature flags, error types, chat models, guardrails. Depends on OpenTelemetry and Pydantic.
- **`packages/uipath-platform`** — HTTP client layer for UiPath Platform APIs. Contains service classes for orchestrator resources (assets, buckets, jobs, processes, queues), action center, context grounding, documents, connections, chat, and guardrails. Depends on `uipath-core`, httpx, and tenacity.

Dependency chain: `uipath` → `uipath-platform` → `uipath-core`. Local editable links are configured via `[tool.uv.sources]`.

## Build & Development Commands

All packages use **uv** for dependency management and **hatch** as the build backend.

```bash
# Install dependencies (run from each package directory)
cd packages/uipath && uv sync --all-extras

# The main package has a justfile (run from packages/uipath/):
just lint        # ruff check + custom httpx linter
just format      # ruff format --check
just validate    # lint + format
just build       # validate + update-agents-md + uv build
just install     # uv sync --all-extras
```

### Linting & Formatting

```bash
# From any package directory:
ruff check .          # Lint (rules: E, F, B, I, D; Google-style docstrings)
ruff format --check . # Format check
ruff check --fix .    # Auto-fix lint issues
ruff format .         # Auto-format

# Custom linter (packages/uipath only):
python scripts/lint_httpx_client.py
```

Ruff config: line-length 88, double quotes, space indent. Docstring rules (D) are disabled for tests. Line length (E501) is ignored globally.

### Type Checking

```bash
# From any package directory:
mypy src tests
```

Uses pydantic mypy plugin. Configured in each package's `pyproject.toml`.

### Running Tests

```bash
# From any package directory:
pytest                           # Run all tests
pytest tests/cli/                # Run a test subdirectory
pytest tests/cli/test_pack.py    # Run a specific file
pytest tests/cli/test_pack.py::test_name  # Run a single test
pytest -x                        # Stop on first failure
```

All packages use pytest with pytest-asyncio (auto mode), pytest-httpx for HTTP mocking, pytest-cov for coverage. Tests are in `tests/` within each package.

### Pre-commit

The repo has a `.pre-commit-config.yaml` with ruff hooks (check + format).

## Key Architecture Details

### Platform Services Pattern (uipath-platform)

Each orchestrator resource follows a two-file pattern in `packages/uipath-platform/src/uipath/platform/orchestrator/`:
- `_<resource>_service.py` — Internal service class with HTTP client logic (httpx calls, URL construction, error handling)
- `<resource>.py` — Public-facing wrapper that delegates to the service class

Service method naming convention:
- `retrieve` — get a single resource by key
- `retrieve_by_[field]` — get a resource by an alternate field
- `list` — get multiple resources

### CLI Architecture (packages/uipath)

The CLI uses **click** and is organized as `cli_<command>.py` files in `src/uipath/_cli/`. Heavy imports are deferred (lazy-loaded) to keep startup fast — do not add top-level imports to `_cli/__init__.py`.

### Agent Framework

`src/uipath/agent/` contains the agent runtime. Agents use Pydantic models for Input/Output schemas.

### Evaluation Framework

`src/uipath/eval/` provides evaluators (ExactMatch, Contains, JsonSimilarity, LLMJudge, Trajectory, ToolCall, Classification) for testing agent quality.

## Code Conventions

- Python 3.11+ required
- Always add type annotations to functions and classes
- Use Google-style docstrings for public APIs
- Use `httpx` for HTTP requests (never `requests`)
- Use `pydantic` for data models
- Tests use pytest only (no unittest module); pytest-asyncio auto mode means async tests don't need `@pytest.mark.asyncio`
