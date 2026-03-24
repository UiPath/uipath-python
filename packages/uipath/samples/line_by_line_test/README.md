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

The sample includes three test cases:

1. **All lines match exactly** - Both evaluators score 1.0
2. **One line doesn't match** - Line-by-line: 0.67, Regular: 0.0 (shows partial credit!)
3. **Single item** - Both evaluators score 1.0

Expected output:
```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┓
┃  Evaluation                   ┃  LineByLineExactMatch  ┃  RegularExactMatch  ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━┩
│  Test all lines match         │                   1.0  │                1.0  │
│  Test when one line doesn't   │                   0.7  │                0.0  │  ← Key difference!
│  Test with single item        │                   1.0  │                1.0  │
├───────────────────────────────┼────────────────────────┼─────────────────────┤
│  Average                      │                   0.9  │                0.7  │
└───────────────────────────────┴────────────────────────┴─────────────────────┘
```

## Configuration

### Evaluator Configuration

The line-by-line evaluator is configured in `evaluations/evaluators/line-by-line-exact-match.json`:

```json
{
  "evaluatorConfig": {
    "name": "LineByLineExactMatch",
    "targetOutputKey": "result",
    "lineByLineEvaluator": true,
    "lineDelimiter": "\n"
  }
}
```

Key options:
- `lineByLineEvaluator`: Enable line-by-line evaluation (default: `false`)
- `lineDelimiter`: Delimiter to split lines (default: `"\n"`)

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
├── main.py                              # Simple agent that outputs one item per line
├── uipath.json                          # Agent configuration
├── pyproject.toml                       # Dependencies (uses TestPyPI)
└── evaluations/
    ├── evaluators/
    │   ├── line-by-line-exact-match.json    # Line-by-line evaluator
    │   └── regular-exact-match.json          # Regular evaluator (for comparison)
    └── eval-sets/
        └── default.json                      # Test cases
```

## Learn More

- [UiPath Python SDK Documentation](https://docs.uipath.com/)
- [Evaluation Framework Guide](../../src/uipath/_resources/eval.md)
