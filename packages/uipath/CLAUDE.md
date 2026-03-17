# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with the main `uipath` package.

## Package Purpose

The top-level SDK package that users `uv pip install`. Contains the CLI (`uipath` command), agent framework, evaluation framework, tracing, telemetry, and function utilities. Depends on `uipath-platform` and `uipath-core`.

## Development Commands

```bash
cd packages/uipath

uv sync --all-extras          # Install dependencies
just lint                     # ruff check + custom httpx linter
just format                   # ruff format --check
just validate                 # lint + format
just build                    # validate + update-agents-md + uv build
just install                  # uv sync --all-extras
just test-lint-httpx          # Test the custom httpx linter

pytest                        # Run all tests
pytest tests/cli/             # Run CLI tests
pytest tests/cli/test_pack.py::test_name  # Single test
ruff check .                  # Lint
ruff format --check .         # Format check
mypy src tests                # Type check
```

### Custom Linter

`scripts/lint_httpx_client.py` enforces httpx client usage patterns. Run with `just lint` or `python scripts/lint_httpx_client.py`.

### AGENTS.md Generation

`scripts/update_agents_md.py` auto-generates `src/uipath/_resources/AGENTS.md` from agent definitions. Run via `just build` or `just update-agents-md`.

## CLI Architecture (`src/uipath/_cli/`)

Uses **click** framework. Commands are organized as `cli_<command>.py` files.

**Critical: lazy imports.** The CLI `__init__.py` defers all heavy imports to keep startup fast (~0.5s). Do NOT add top-level imports to `_cli/__init__.py`.

### Commands

| File | Command | Purpose |
|------|---------|---------|
| `cli_new.py` | `new` | Create new project |
| `cli_init.py` | `init` | Initialize project (generates entry-points.json) |
| `cli_pack.py` | `pack` | Package into .nupkg |
| `cli_publish.py` | `publish` | Publish to Orchestrator feed |
| `cli_deploy.py` | `deploy` | Pack + publish in one step |
| `cli_run.py` | `run` | Execute a project locally |
| `cli_auth.py` | `auth` | Browser-based authentication |
| `cli_invoke.py` | `invoke` | Invoke a specific entrypoint |
| `cli_eval.py` | `eval` | Run evaluations |
| `cli_push.py` | `push` | Push to remote storage |
| `cli_pull.py` | `pull` | Pull from remote storage |
| `cli_dev.py` | `dev` | Development server mode |
| `cli_add.py` | `add` | Add resource/dependency |
| `cli_server.py` | `server` | Run as server |
| `cli_register.py` | `register` | Register resource |
| `cli_debug.py` | `debug` | Debug execution |

Sub-commands: `services/cli_assets.py` (asset management), `services/cli_buckets.py` (bucket management).

## Agent Framework (`src/uipath/agent/`)

- **`models/`** — Agent definition models (`agent.py` is the main one, ~43KB), evaluation config, legacy compat
- **`utils/`** — `load_agent_definition`, `create_agent_project`, `download_agent_project`, token counting

## Evaluation Framework (`src/uipath/eval/`)

Plugin-based evaluator registration system with deterministic and LLM-based evaluators.

- **`evaluators/`** — 11 active evaluators: ExactMatch, Contains, JsonSimilarity, BinaryClassification, MulticlassClassification, LLMJudgeOutput, LLMJudgeTrajectory, ToolCallOrder/Args/Count/Output. Plus ~7 legacy evaluators.
- **`mocks/`** — LLM mocking, input mocking, cache management, mockito integration. Key exports: `mockable`, `UiPathMockRuntime`, `MockingContext`.
- **`runtime/`** — `UiPathEvalRuntime`, `UiPathEvalContext`, `evaluate()` entry point, parallelization, exporters.
- **`models/`** — `AgentExecution`, `EvaluationResult`, `ToolCall`, `LLMResponse`, evaluator type enums.

## Functions Module (`src/uipath/functions/`)

- `UiPathFunctionsRuntime` / `UiPathDebugFunctionsRuntime` — function execution runtimes
- `UiPathFunctionsRuntimeFactory` — factory pattern for runtime creation
- `graph_builder.py` — function graph construction
- `schema_gen.py` — schema generation from function definitions

## Tracing (`src/uipath/tracing/`)

OpenTelemetry integration with `JsonLinesFileExporter`, `LlmOpsHttpExporter`, `LiveTrackingSpanProcessor`. The `traced` decorator is re-exported from `uipath-core`.

## Telemetry (`src/uipath/telemetry/`)

Application Insights tracking: `track()`, `track_event()`, `is_telemetry_enabled()`, `flush_events()`.

## Bundled Resources (`src/uipath/_resources/`)

Documentation files bundled with the package: `AGENTS.md` (auto-generated), `CLAUDE.md`, `CLI_REFERENCE.md`, `SDK_REFERENCE.md`, `REQUIRED_STRUCTURE.md`, `eval.md`, `new-agent.md`.

## Test Structure

```
tests/
├── agent/          # Agent models, react prompts, utils
├── cli/            # CLI command tests (largest test suite)
│   ├── chat/       # Chat bridge tests
│   ├── contract/   # SDK/CLI alignment tests
│   ├── eval/       # Evaluation tests (30+ files, mocks, integration)
│   ├── evaluators/ # Legacy evaluator tests
│   ├── integration/# End-to-end tests
│   ├── mocks/      # Mock fixtures
│   ├── models/     # Model tests
│   ├── unit/       # Unit tests
│   └── utils/      # Utility tests
├── evaluators/     # General evaluator tests
├── functions/      # Functions runtime tests
├── resource_overrides/ # Resource override tests
├── sdk/            # SDK functionality tests
├── telemetry/      # Telemetry tests
└── tracing/        # Tracing integration tests
```
