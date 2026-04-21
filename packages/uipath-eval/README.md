# uipath-eval

Standalone evaluator logic extracted from the `uipath` SDK.

Use this package in `python-eval-workers` and other services that need
evaluator logic without the full UiPath SDK overhead.

## Install

```bash
pip install uipath-eval
```

For LLM-based evaluators (llm-as-judge, trajectory):

```bash
pip install "uipath-eval[llm]"
```

## Usage

```python
from uipath_eval import ExactMatchEvaluator, LLMJudgeOutputEvaluator
from uipath_eval.models import EvaluationResult
```

## What's here

- `uipath_eval.evaluators` — all evaluator implementations
- `uipath_eval.models` — evaluation data models
- `uipath_eval.runtime` — pure asyncio/stdlib runtime utilities

## What's NOT here

`UiPathEvalRuntime`, `UiPathEvalContext`, and `evaluate()` depend on
`uipath.runtime` and stay in `uipath.eval`. Use `uipath` if you need
the full eval pipeline with runtime integration.
