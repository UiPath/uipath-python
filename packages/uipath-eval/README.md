# uipath-eval

Evaluation framework for UiPath agents, extracted from the main `uipath` SDK so
it can be consumed standalone (for example by the python eval worker in the
agents backend) without pulling in the CLI and the rest of the SDK.

Provides the `uipath.eval` namespace package:

- **`uipath.eval.evaluators`** — deterministic evaluators (ExactMatch, Contains,
  JsonSimilarity, classification, tool-call order/args/count/output) and
  LLM-based evaluators (LLM-judge output/trajectory), plus their legacy
  counterparts and the evaluator factory/registration system.
- **`uipath.eval.models`** — evaluation sets, evaluation results, score types,
  agent execution models.
- **`uipath.eval.mocks`** — the `@mockable` decorator, LLM tool/input mocking,
  mockito integration, and response caching used by simulation runs.
- **`uipath.eval.runtime`** — `UiPathEvalRuntime`, `UiPathEvalContext`, the
  `evaluate()` entry point, eval events, parallelization, and exporters.

## Installation

```bash
uv pip install uipath-eval
```

Import paths are unchanged from when this code lived in the `uipath` package:

```python
from uipath.eval.evaluators import ExactMatchEvaluator
from uipath.eval.models.evaluation_set import EvaluationSet
from uipath.eval.runtime import UiPathEvalContext, evaluate
```

## Development

```bash
cd packages/uipath-eval

uv sync --all-extras          # Install dependencies
pytest                        # Run all tests
ruff check .                  # Lint
ruff format --check .         # Format check
mypy src                      # Type check
```
