# AGENTS.md

This file provides guidance to AI agents when working with code in this repository.

## Project Overview

UiPath Python SDK and CLI for programmatic interaction with UiPath Cloud Platform services. The package provides both:
- **SDK**: Python API for services (processes, assets, buckets, jobs, context grounding, etc.)
- **CLI**: Command-line tool for creating, packaging, debugging, and deploying automation projects to UiPath Cloud Platform

## Development Commands

### Environment Setup
```bash
# Create virtual environment
uv venv

# Activate virtual environment
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\Activate.ps1  # Windows PowerShell

# Install dependencies
uv sync --all-extras --no-cache
```

### Build & Quality Checks
```bash
# Lint code (includes custom httpx client linting)
just lint
# or: ruff check .

# Format code
just format
# or: ruff format --check .

# Run both lint and format
just validate

# Build package (includes validation and agent markdown updates)
just build
# or: uv build

# Run pre-commit hooks manually
pre-commit run --all-files
```

### Testing
```bash
# Run all tests with coverage
pytest

# Run specific test file
pytest tests/sdk/services/test_assets_service.py

# Run specific test function
pytest tests/sdk/services/test_assets_service.py::test_retrieve_asset

# Run tests in specific directory
pytest tests/sdk/

# Run with verbose output
pytest -v

# Run async tests (uses pytest-asyncio)
pytest tests/sdk/services/test_async_operations.py
```

### CLI Development
```bash
# Test CLI commands locally (must be in venv)
uipath --help
uipath auth
uipath init
uipath pack
uipath publish

# Install SDK in editable mode for local development
uv add --editable /path/to/uipath-python
```

## Architecture

### Core Components

**SDK Entry Point (`src/uipath/_uipath.py`)**
- `UiPath` class: Main SDK interface providing property-based access to all services
- Services instantiated lazily via `@property` methods
- Shared `Config` and `ExecutionContext` passed to all services

**Configuration (`src/uipath/_config.py`)**
- `Config`: Holds `base_url` and `secret` for authentication
- Credentials resolved from: constructor args → env vars (UIPATH_URL, UIPATH_ACCESS_TOKEN) → .env file

**Execution Context (`src/uipath/_execution_context.py`)**
- Manages runtime environment info: job instance ID, job key, robot key
- Reads from environment variables set by UiPath Robot during execution
- Used for job tracking and telemetry

**Folder Context (`src/uipath/_folder_context.py`)**
- Manages folder scope for UiPath resources (processes, assets, etc.)
- Provides `folder_headers` for API requests based on UIPATH_FOLDER_KEY or UIPATH_FOLDER_PATH
- Inherited by services that need folder-scoped operations

**Base Service (`src/uipath/_services/_base_service.py`)**
- All services extend `BaseService`
- Provides both sync (`httpx.Client`) and async (`httpx.AsyncClient`) HTTP clients
- Automatic retry logic for 5xx errors and connection timeouts using tenacity
- Standard headers (authorization, user-agent) applied to all requests
- Request overrides manager for testing/mocking

### Services Architecture (`src/uipath/_services/`)

Each service follows this pattern:
1. Extends `BaseService` (some also extend `FolderContext` for folder-scoped operations)
2. Constructor: `__init__(self, config: Config, execution_context: ExecutionContext, ...)`
3. Methods use standard naming:
   - `retrieve(key)` - Get single resource by primary identifier
   - `retrieve_by_[field](value)` - Get resource by alternate field
   - `list(filters)` - Get multiple resources
   - `create(data)` - Create new resource
   - `update(key, data)` - Modify existing resource
   - `delete(key)` - Remove resource

**Key Services:**
- `ApiClient`: Direct HTTP access for custom requests
- `ProcessesService`: Execute and manage automation processes
- `AssetsService`: Access shared variables/credentials
- `JobsService`: Monitor job execution
- `BucketsService`: Cloud storage operations
- `ContextGroundingService`: AI-enabled semantic search and knowledge grounding
- `ConnectionsService`: External system integrations
- `QueuesService`: Transaction queue management
- `ActionsService`: Action Center task management

### CLI Architecture (`src/uipath/_cli/`)

**Entry Point (`__init__.py`)**
- Click-based CLI with multiple commands
- Commands: `new`, `init`, `pack`, `publish`, `run`, `deploy`, `auth`, `invoke`, `push`, `pull`, `eval`, `dev`, `debug`
- Loads `.env` automatically and adds CWD to Python path

**Key CLI Modules:**
- `cli_auth.py`: OAuth authentication flow, creates/updates .env file
- `cli_init.py`: Creates uipath.json config for project
- `cli_pack.py`: Packages project into .nupkg for UiPath deployment
- `cli_publish.py`: Uploads package to Orchestrator
- `cli_run.py`: Local execution with input args
- `cli_debug.py`: Debug mode execution
- `_templates/`: Project scaffolding templates
- `_push/`: Package deployment logic
- `_evals/`: Evaluation framework for agent testing

### Agent Framework (`src/uipath/agent/`)

Supports building AI agents for UiPath platform:
- `conversation/`: Conversational agent patterns
- `react/`: ReAct (Reasoning + Acting) agent implementation
- `models/`: Agent definition schemas and data models

### Telemetry & Tracing (`src/uipath/tracing/`, `src/uipath/telemetry/`)

- OpenTelemetry integration for distributed tracing
- Azure Monitor exporters for cloud telemetry
- `@traced` decorator for automatic span creation

### Utilities (`src/uipath/_utils/`)

- `_auth.py`: Credential resolution (OAuth, PAT tokens)
- `_url.py`: URL parsing and validation for UiPath endpoints
- `_logs.py`: Structured logging setup
- `_endpoint.py`: API endpoint construction
- `_infer_bindings.py`: Type inference for agent bindings
- `_request_spec.py`: Request specification helpers
- `_ssl_context.py`: SSL/TLS configuration for httpx

## Coding Standards

### Type Annotations
- **Required** on all functions and classes (public and internal)
- Include return types explicitly
- Use `Optional[T]` for nullable values
- Use `Union[A, B]` for multiple types (or `A | B` for Python 3.10+)

### Docstrings
- **Required** for all public functions and classes
- Use **Google-style convention**
- Reference https://docs.uipath.com for UiPath concepts
- Example:
  ```python
  def retrieve(self, name: str) -> Asset:
      """Retrieve an asset by name.

      Args:
          name: The name of the asset to retrieve.

      Returns:
          The asset object.

      Raises:
          AssetNotFoundError: If the asset does not exist.
      """
  ```

### Service Method Naming
- `retrieve` not `retrieve_user` (method is already scoped to service)
- `retrieve_by_email` for alternate lookups
- `list` not `list_users`
- This applies to core SDK methods only, not internal utilities

### Testing
- Use **pytest only** (no unittest module)
- All tests in `./tests` directory mirroring `./src/uipath` structure
- Tests require type annotations and docstrings
- Import pytest types when TYPE_CHECKING:
  ```python
  from typing import TYPE_CHECKING

  if TYPE_CHECKING:
      from _pytest.capture import CaptureFixture
      from _pytest.fixtures import FixtureRequest
      from _pytest.logging import LogCaptureFixture
      from _pytest.monkeypatch import MonkeyPatch
      from pytest_mock.plugin import MockerFixture
  ```
- Use pytest plugins: pytest-asyncio, pytest-httpx, pytest-cov, pytest-mock
- Create `__init__.py` files in test directories as needed

### Code Style
- Line length: 88 characters (Ruff default)
- 4-space indentation
- Double quotes for strings
- Ruff linting rules: E (errors), F (pyflakes), B (bugbear), I (isort), D (pydocstyle)
- Google-style docstrings enforced via ruff (convention = "google")
- Tests and docs exempt from docstring requirements

### Error Handling
- Robust error handling with context capture
- Custom exceptions in `src/uipath/models/errors.py` and `exceptions.py`
- Use `EnrichedException` for enhanced error details

### File Organization
- Source: `src/uipath/`
- Tests: `tests/` (mirror source structure)
- Docs: `docs/`
- Scripts: `scripts/` (build utilities, linters)
- Samples: `samples/` (excluded from linting)
- Test cases: `testcases/` (excluded from linting)

## Important Notes

### Custom Linters
- Custom linter enforces httpx client usage patterns: `scripts/lint_httpx_client.py`
- Run via `just lint` or `python scripts/lint_httpx_client.py`

### Package Building
- `pyproject.toml` must include description (avoid: &, <, >, ", ', ;) and author info
- Build process updates agent markdown: `scripts/update_agents_md.py`
- Uses Hatchling build backend

### Dependencies
- **uv**: Fast Python package manager (replaces pip/poetry)
- **httpx**: Async HTTP client (not requests)
- **pydantic**: Data validation and settings
- **click**: CLI framework
- **tenacity**: Retry logic
- **python-dotenv**: .env file support
- **OpenTelemetry**: Distributed tracing

### Pre-commit Hooks
- Ruff format and lint run automatically on commit
- Configure via `.pre-commit-config.yaml`

### Environment Variables
SDK requires:
- `UIPATH_URL`: Full URL to tenant (e.g., https://cloud.uipath.com/org/tenant)
- `UIPATH_ACCESS_TOKEN`: Personal access token or OAuth token

Optional (set by UiPath Robot):
- `UIPATH_JOB_ID`, `UIPATH_JOB_KEY`: Job tracking
- `UIPATH_ROBOT_KEY`: Robot identification
- `UIPATH_FOLDER_KEY` or `UIPATH_FOLDER_PATH`: Folder scope
