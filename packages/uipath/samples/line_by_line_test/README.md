# Line-by-Line Evaluation Sample

This sample demonstrates the line-by-line evaluation feature for output evaluators.

## Overview

Line-by-line evaluation allows evaluators to:
- Split multi-line outputs by a configurable delimiter (e.g., `\n`)
- Evaluate each line independently
- Provide partial credit based on the percentage of correct lines
- Return detailed per-line feedback

## Features Demonstrated

- **Partial Credit Scoring**: Get 0.67 for 2/3 correct lines instead of 0.0
- **Per-Line Feedback**: See exactly which lines passed or failed
- **Configurable Delimiter**: Use `\n`, `|`, or any custom delimiter
- **Comparison**: Side-by-side comparison with regular evaluation

## Installation

This sample uses the UiPath package from TestPyPI:

```bash
# Install dependencies
uv sync

# Or manually install
uv pip install --index-url https://test.pypi.org/simple/ "uipath>=2.10.30.dev1014810000,<2.10.30.dev1014820000"
```

## Usage

### Run the agent

```bash
uv run uipath run main '{"items": ["apple", "banana", "cherry"]}'
```

### Run evaluations

```bash
uv run uipath eval main evaluations/eval-sets/default.json --workers 1
```

## Evaluation Results

The sample includes three test cases with five evaluators:

### ExactMatch Evaluators
- **LineByLineExactMatch** - New evaluator with line-by-line support
- **RegularExactMatch** - New evaluator without line-by-line (for comparison)
- **LegacyLineByLineExactMatch** - Legacy evaluator with line-by-line support

### Contains Evaluators
- **LineByLineContains** - New evaluator with line-by-line support (checks if each line contains the search text)
- **RegularContains** - New evaluator without line-by-line (checks if the entire output contains the search text)

Test cases:
1. **All lines match exactly** - All evaluators score 1.0
2. **One line doesn't match** - Line-by-line ExactMatch: 0.67, Regular ExactMatch: 0.0 (shows partial credit!)
3. **Single item** - All evaluators score 1.0

Expected output (showing ExactMatch evaluators):
```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  Evaluation                   ┃  LineByLineExactMatch  ┃  RegularExactMatch  ┃  LegacyLineByLineExactMatch  ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│  Test all lines match         │                   1.0  │                1.0  │                          1.0  │
│  Test when one line doesn't   │                   0.7  │                0.0  │                          0.7  │  ← Key difference!
│  Test with single item        │                   1.0  │                1.0  │                          1.0  │
├───────────────────────────────┼────────────────────────┼─────────────────────┼───────────────────────────────┤
│  Average                      │                   0.9  │                0.7  │                          0.9  │
└───────────────────────────────┴────────────────────────┴─────────────────────┴───────────────────────────────┘
```

Contains evaluators will all score 1.0 since all test outputs contain "Item:".

## Configuration

### Evaluator Configuration

#### New Evaluators (Version-based)

The line-by-line evaluator is configured in `evaluations/evaluators/line-by-line-exact-match.json`:

```json
{
  "version": "1.0",
  "evaluatorTypeId": "uipath-exact-match",
  "evaluatorConfig": {
    "name": "LineByLineExactMatch",
    "targetOutputKey": "result",
    "lineByLineEvaluator": true,
    "lineDelimiter": "\n"
  }
}
```

#### Legacy Evaluators (Category/Type-based)

Legacy evaluators also support line-by-line evaluation in `evaluations/evaluators/legacy-line-by-line-exact-match.json`:

```json
{
  "category": "Deterministic",
  "type": "Equals",
  "name": "LegacyLineByLineExactMatch",
  "targetOutputKey": "result",
  "lineByLineEvaluation": true,
  "lineDelimiter": "\n"
}
```

#### Contains Evaluators

The Contains evaluator checks if the output contains a specific search text. In line-by-line mode, it checks each line independently:

**Line-by-line Contains** (`evaluations/evaluators/line-by-line-contains.json`):
```json
{
  "version": "1.0",
  "evaluatorTypeId": "uipath-contains",
  "evaluatorConfig": {
    "name": "LineByLineContains",
    "target_output_key": "result",
    "line_by_line_evaluator": true,
    "line_delimiter": "\n",
    "case_sensitive": false,
    "negated": false
  }
}
```

**Regular Contains** (`evaluations/evaluators/regular-contains.json`):
```json
{
  "version": "1.0",
  "evaluatorTypeId": "uipath-contains",
  "evaluatorConfig": {
    "name": "RegularContains",
    "target_output_key": "result",
    "line_by_line_evaluator": false,
    "case_sensitive": false,
    "negated": false
  }
}
```

In evaluation criteria, specify the search text:
```json
{
  "LineByLineContains": {
    "searchText": "Item:"
  }
}
```

**Behavior difference**:
- **Line-by-line**: Checks if each line contains "Item:", gives partial credit (e.g., 2/3 if one line is missing it)
- **Regular**: Checks if the entire output contains "Item:" at least once, returns 1.0 or 0.0

Key options for all evaluator types:
- `lineByLineEvaluator`/`lineByLineEvaluation`: Enable line-by-line evaluation (default: `false`)
- `lineDelimiter`: Delimiter to split lines (default: `"\n"`)
- `case_sensitive`: Case-sensitive comparison (default: `false` for Contains, `true` for ExactMatch)
- `negated`: Invert the result (default: `false`, only for Contains)

### Custom Delimiters

You can use any delimiter:

```json
{
  "evaluatorConfig": {
    "lineByLineEvaluator": true,
    "lineDelimiter": "|"  // Pipe-separated values
  }
}
```

## File Structure

```
line_by_line_test/
├── main.py                                      # Simple agent that outputs one item per line
├── uipath.json                                  # Agent configuration
├── pyproject.toml                               # Dependencies (uses TestPyPI)
└── evaluations/
    ├── evaluators/
    │   ├── line-by-line-exact-match.json           # New line-by-line ExactMatch evaluator
    │   ├── regular-exact-match.json                 # New regular ExactMatch evaluator
    │   ├── legacy-line-by-line-exact-match.json    # Legacy line-by-line ExactMatch evaluator
    │   ├── line-by-line-contains.json              # New line-by-line Contains evaluator
    │   └── regular-contains.json                    # New regular Contains evaluator
    └── eval-sets/
        └── default.json                             # Test cases with all 5 evaluators
```

## Learn More

- [UiPath Python SDK Documentation](https://docs.uipath.com/)
- [Evaluation Framework Guide](../../src/uipath/_resources/eval.md)
