# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with the `uipath-eval` package.

## Package Purpose

The evaluation framework for UiPath agents, providing the `uipath.eval` namespace package. Extracted from the main `uipath` SDK so consumers (e.g. the python eval worker in the agents backend) can depend on evaluators without the CLI and the rest of the SDK. Depends on `uipath-core`, `uipath-platform`, and `uipath-runtime`.

## Development Commands

```bash
cd packages/uipath-eval

uv sync --all-extras          # Install dependencies
pytest                        # Run all tests
pytest tests/eval/mocks/      # Run a test subdirectory
ruff check .                  # Lint
ruff format --check .         # Format check
mypy src                      # Type check
```

No justfile exists for this package — run commands directly.

## Module Layout (`src/uipath/eval/`)

| Module | Purpose |
|--------|---------|
| `evaluators/` | Deterministic evaluators (ExactMatch, Contains, JsonSimilarity, classification, tool-call order/args/count/output), LLM-judge evaluators, legacy evaluators, evaluator factory + registration |
| `models/` | `EvaluationSet`, `EvaluationItem`, `EvaluationResult`, `AgentExecution`, score types |
| `mocks/` | `@mockable` decorator, LLM tool/input mocking, mockito integration, response caching, `UiPathMockRuntime` |
| `runtime/` | `UiPathEvalRuntime`, `UiPathEvalContext`, `evaluate()` entry point, eval events, parallelization, exporters |
| `helpers.py` | `EvalHelpers` (eval set loading/migration), `get_agent_model()` |

## Constraints

- This is a **namespace package**: `src/uipath/` has no `__init__.py`; only `src/uipath/eval/` does. Import paths are unchanged from when the code lived in the main SDK (`from uipath.eval...`).
- Do not import from the main `uipath` package internals (`uipath._cli`, `uipath._utils`, `uipath.agent`, ...) — only `uipath.core`, `uipath.platform`, and `uipath.runtime` are available here. The main `uipath` package depends on this one, not vice versa.
- Structured output across model providers must use function calling, not `response_format` (Claude returns prose, Gemini returns empty content for `response_format` on the normalized gateway — see `mocks/_structured_output.py`).
- The CLI-facing progress reporters (`_progress_reporter.py`, `_console_progress_reporter.py`) intentionally stay in `packages/uipath/src/uipath/_cli/_evals/` — they are CLI infrastructure, not part of this package.
