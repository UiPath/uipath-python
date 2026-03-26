# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with the `uipath-platform` package.

## Package Purpose

HTTP client layer for UiPath Platform APIs. Provides typed service classes for all orchestrator and platform resources. Depends on `uipath-core`, httpx, tenacity, and pydantic.

## Development Commands

```bash
cd packages/uipath-platform

uv sync --all-extras          # Install dependencies
pytest                        # Run all tests
pytest tests/services/test_assets_service.py  # Single test file
ruff check .                  # Lint
ruff format --check .         # Format check
mypy src tests                # Type check
```

No justfile exists for this package — run commands directly.

## Entry Point: `UiPath` Class

`_uipath.py` defines the main `UiPath` class that exposes all services as properties:

```python
from uipath.platform import UiPath
sdk = UiPath()
sdk.assets              # AssetsService
sdk.attachments         # AttachmentsService
sdk.processes           # ProcessesService
sdk.buckets             # BucketsService
sdk.queues              # QueuesService
sdk.jobs                # JobsService
sdk.folders             # FolderService
sdk.tasks               # TasksService (Action Center)
sdk.connections         # ConnectionsService
sdk.context_grounding   # ContextGroundingService
sdk.documents           # DocumentsService
sdk.entities            # EntitiesService
sdk.llm                 # UiPathLlmChatService
sdk.llm_openai          # UiPathOpenAIService
sdk.conversational      # ConversationsService
sdk.guardrails          # GuardrailsService
sdk.agenthub            # AgentHubService
sdk.mcp                 # McpService
sdk.resource_catalog    # ResourceCatalogService
sdk.automation_tracker  # AutomationTrackerService
```

### Authentication

Credentials can be provided via constructor parameters or environment variables (`UIPATH_URL`, `UIPATH_ACCESS_TOKEN`). Two auth modes are supported:

- **User authentication** — provide `base_url` and `secret` (access token), or set them via env vars
- **S2S (service-to-service)** — provide `client_id` and `client_secret` (both required together), optionally with `scope`; uses `ExternalApplicationService` internally to exchange for an access token

Configuration is validated with Pydantic; missing `base_url` raises `BaseUrlMissingError`, missing `secret` raises `SecretMissingError`.

## Service Architecture

### Two-File Pattern (orchestrator/)

Each orchestrator resource uses two files:
- **`_<resource>_service.py`** — Internal service class extending `BaseService` and `FolderContext`. Contains HTTP logic (httpx calls, URL construction, retry, error handling). Methods decorated with `@traced` and `@resource_override`.
- **`<resource>.py`** — Public Pydantic models for the resource.

### BaseService (`common/_base_service.py`)

All services inherit from `BaseService` which provides:
- `request()` / `request_async()` — HTTP methods with tenacity-based retry (exponential backoff)
- Automatic exception enrichment via `EnrichedException`
- User-agent tracking and span utilities

### FolderContext (`common/_folder_context.py`)

Manages folder scoping (by `folder_key` or `folder_path`) for orchestrator operations.

### Method Naming Convention

- `retrieve` — get single resource by key
- `retrieve_by_[field]` — get by alternate field
- `list` — get multiple resources

### Sync + Async

Services provide both sync and async variants (e.g., `.invoke()` and `.invoke_async()`).

## Modules Beyond Orchestrator

| Module | Purpose |
|--------|---------|
| `action_center/` | Task management for human-in-the-loop workflows |
| `agenthub/` | System agents and LLM model discovery |
| `automation_tracker/` | Business Transaction Service (BTS) for Process Mining |
| `chat/` | LLM gateway, conversations, throttling |
| `connections/` | External connection management |
| `context_grounding/` | RAG services (DeepRAG, batch RAG, ephemeral indexes) |
| `documents/` | Document Understanding (IXP) |
| `entities/` | Data Service entity management |
| `guardrails/` | LLM output guardrails |
| `resource_catalog/` | Resource discovery and metadata |
| `resume_triggers/` | HITL trigger creation/reading protocols |
| `common/` | Shared base classes, config, auth, retry, paging, validation |
| `errors/` | Custom exceptions (`EnrichedException`, `FolderNotFoundException`, `BaseUrlMissingError`, etc.) |

## Test Structure

All tests are under `tests/services/` with one test file per service. Tests use `pytest-httpx` for HTTP mocking.

### Key Test Fixtures (`tests/services/conftest.py`)

- `base_url` — returns `"https://test.uipath.com"`
- `config` — `UiPathApiConfig` instance
- `execution_context` — `UiPathExecutionContext` with mocked `UIPATH_ROBOT_KEY`
- `mock_env_vars` — standard mock env vars (URL, tokens, IDs)
- Service-specific fixtures (e.g., `jobs_service`) built from config + execution_context
