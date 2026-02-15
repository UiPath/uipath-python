---
allowed-tools: Bash, Read, Write, Edit, Glob
description: Create and run agent evaluations
---

I'll help you create and run evaluations for your UiPath agent.

## Step 1: Check project setup

Let me check your project structure:

!ls -la evaluations/ entry-points.json 2>/dev/null || echo "NEEDS_SETUP"

# Check if schemas might be stale (main.py newer than entry-points.json)
!if [ -f main.py ] && [ -f entry-points.json ] && [ main.py -nt entry-points.json ]; then echo "SCHEMAS_MAY_BE_STALE"; fi

### If NEEDS_SETUP

If `entry-points.json` doesn't exist, initialize the project first:

!uv run uipath init

Then re-run this skill.

### If SCHEMAS_MAY_BE_STALE

Your `main.py` is newer than `entry-points.json`. Refresh schemas:

!uv run uipath init --no-agents-md-override

## Step 2: What would you like to do?

1. **Create new eval set** - Set up evaluations from scratch
2. **Add test case** - Add a test to existing eval set
3. **Run evaluations** - Execute tests and see results
4. **Analyze failures** - Debug failing tests

---

## Creating an Eval Set

First, create the directory structure:

!mkdir -p evaluations/eval-sets evaluations/evaluators

Read the agent's Input/Output schema from entry-points.json to understand the data types.

### Evaluator Selection Guide

| If your output is... | Use this evaluator | evaluatorTypeId |
|---------------------|-------------------|-----------------|
| Exact string/number | `ExactMatchEvaluator` | `uipath-exact-match` |
| Contains key phrases | `ContainsEvaluator` | `uipath-contains` |
| Semantically correct | `LLMJudgeOutputEvaluator` | `uipath-llm-judge-output-semantic-similarity` |
| JSON with numbers | `JsonSimilarityEvaluator` | `uipath-json-similarity` |

### Step 1: Create Evaluator Config Files

**Each evaluator needs a JSON config file** in `evaluations/evaluators/`.

**ExactMatchEvaluator** (`evaluations/evaluators/exact-match.json`):
```json
{
  "version": "1.0",
  "id": "ExactMatchEvaluator",
  "name": "ExactMatchEvaluator",
  "description": "Checks for exact output match",
  "evaluatorTypeId": "uipath-exact-match",
  "evaluatorConfig": {
    "name": "ExactMatchEvaluator",
    "targetOutputKey": "*"
  }
}
```

**LLMJudgeOutputEvaluator** (`evaluations/evaluators/llm-judge-output.json`):
```json
{
  "version": "1.0",
  "id": "LLMJudgeOutputEvaluator",
  "name": "LLMJudgeOutputEvaluator",
  "description": "Uses LLM to judge semantic similarity",
  "evaluatorTypeId": "uipath-llm-judge-output-semantic-similarity",
  "evaluatorConfig": {
    "name": "LLMJudgeOutputEvaluator",
    "model": "gpt-4o-mini-2024-07-18"
  }
}
```

**JsonSimilarityEvaluator** (`evaluations/evaluators/json-similarity.json`):
```json
{
  "version": "1.0",
  "id": "JsonSimilarityEvaluator",
  "name": "JsonSimilarityEvaluator",
  "description": "Compares JSON structures",
  "evaluatorTypeId": "uipath-json-similarity",
  "evaluatorConfig": {
    "name": "JsonSimilarityEvaluator",
    "targetOutputKey": "*"
  }
}
```

**ContainsEvaluator** (`evaluations/evaluators/contains.json`):
```json
{
  "version": "1.0",
  "id": "ContainsEvaluator",
  "name": "ContainsEvaluator",
  "description": "Checks if output contains text",
  "evaluatorTypeId": "uipath-contains",
  "evaluatorConfig": {
    "name": "ContainsEvaluator"
  }
}
```

### Step 2: Create Eval Set

**Eval Set Template** (`evaluations/eval-sets/default.json`):
```json
{
  "version": "1.0",
  "id": "default-eval-set",
  "name": "Default Evaluation Set",
  "evaluatorRefs": ["ExactMatchEvaluator"],
  "evaluations": [
    {
      "id": "test-1",
      "name": "Test description",
      "inputs": {
        "field": "value"
      },
      "evaluationCriterias": {
        "ExactMatchEvaluator": {
          "expectedOutput": {
            "result": "expected value"
          }
        }
      }
    }
  ]
}
```

**Important notes:**
- `evaluatorRefs` must list ALL evaluators used in any test case
- Each evaluator in `evaluatorRefs` needs a matching JSON config in `evaluations/evaluators/`
- `evaluationCriterias` keys must match entries in `evaluatorRefs`
- Use `expectedOutput` for most evaluators
- LLM evaluators need `model` in their config. Available models are defined in the SDK's `ChatModels` class (`uipath.platform.chat.ChatModels`):
  - `gpt-4o-mini-2024-07-18` (recommended for cost-efficiency)
  - `gpt-4o-2024-08-06` (higher quality, higher cost)
  - `o3-mini-2025-01-31` (latest reasoning model)
  - Model availability varies by region and tenant configuration
  - Check your UiPath Automation Cloud portal under AI Trust Layer for available models in your region

---

## Adding a Test Case

When adding a test to an existing eval set:

1. Read the existing eval set
2. Check which evaluators are in `evaluatorRefs`
3. Add the new test to `evaluations` array
4. If using a new evaluator, add it to `evaluatorRefs`

### Test Case Template

```json
{
  "id": "test-{n}",
  "name": "Description of what this tests",
  "inputs": { },
  "evaluationCriterias": {
    "EvaluatorName": {
      "expectedOutput": { }
    }
  }
}
```

---

## Running Evaluations

First, read entry-points.json to get the entrypoint name (e.g., `main`):

!uv run uipath eval main evaluations/eval-sets/default.json --output-file eval-results.json

**Note:** Replace `main` with your actual entrypoint from entry-points.json.

### Analyze Results

After running, read `eval-results.json` and show:
- Pass/fail summary table
- For failures: expected vs actual output
- Suggestions for fixing or changing evaluators

### Results Format

```json
{
  "evaluationSetResults": [{
    "evaluationRunResults": [
      {
        "evaluationId": "test-1",
        "evaluatorId": "ExactMatchEvaluator",
        "result": { "score": 1.0 },
        "errorMessage": null
      }
    ]
  }]
}
```

- Score 1.0 = PASS
- Score < 1.0 = FAIL (show expected vs actual)
- errorMessage present = ERROR (show message)

---

## Evaluator Reference

### Deterministic Evaluators

**ExactMatchEvaluator** - Exact output matching
```json
"ExactMatchEvaluator": {
  "expectedOutput": { "result": "exact value" }
}
```

**ContainsEvaluator** - Output contains substring
```json
"ContainsEvaluator": {
  "searchText": "must contain this"
}
```

**JsonSimilarityEvaluator** - JSON comparison with tolerance
```json
"JsonSimilarityEvaluator": {
  "expectedOutput": { "value": 10.0 }
}
```

### LLM-Based Evaluators

**LLMJudgeOutputEvaluator** - Semantic correctness
```json
"LLMJudgeOutputEvaluator": {
  "expectedOutput": { "summary": "Expected semantic meaning" }
}
```

**LLMJudgeTrajectoryEvaluator** - Validate agent reasoning
```json
"LLMJudgeTrajectoryEvaluator": {
  "expectedAgentBehavior": "The agent should first fetch data, then process it"
}
```

---

## Common Issues

### "No evaluations found"
- Check `evaluations/eval-sets/` directory exists
- Verify JSON file is valid

### Evaluator not found
- Each evaluator needs a JSON config file in `evaluations/evaluators/`
- Config file must have correct `evaluatorTypeId` (see templates above)
- Config file must have `name` field at root level
- LLM evaluators need `model` in `evaluatorConfig`

### Evaluator skipped
- Ensure evaluator is listed in root `evaluatorRefs` array
- Check evaluator config file exists in `evaluations/evaluators/`

### Schema mismatch
- Run `uv run uipath init --no-agents-md-override` to refresh schemas
- Check `entry-points.json` matches your Input/Output models
