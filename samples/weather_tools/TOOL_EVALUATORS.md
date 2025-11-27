# Tool Call Evaluators

This document explains the tool call evaluators available in the weather_tools sample and how to use them for trajectory evaluation.

## Overview

Tool call evaluators validate specific aspects of how tools are invoked during agent execution. They extract tool information from OpenTelemetry spans and compare against expected criteria.

## Available Evaluators

### 1. ToolCallCountEvaluator

**Purpose**: Validates that tools are called the expected number of times.

**Configuration**: `evaluations/evaluators/tool-call-count.json`

**Example Usage**:
```json
"ToolCallCountEvaluator": {
  "toolCallsCount": {
    "get_temperature": ["=", 1],
    "get_weather_condition": ["=", 1],
    "get_humidity": ["=", 1]
  }
}
```

**Supported Operators**:
- `"="` - Exactly equal to
- `">"` - Greater than
- `"<"` - Less than
- `">="` - Greater than or equal to
- `"<="` - Less than or equal to
- `"!="` - Not equal to

**Use Cases**:
- Ensure a tool is called exactly once
- Verify a tool is called at least N times
- Validate a tool is not called more than N times

### 2. ToolCallOrderEvaluator

**Purpose**: Validates that tools are called in the correct sequence.

**Configuration**: `evaluations/evaluators/tool-call-order.json`

**Example Usage**:
```json
"ToolCallOrderEvaluator": {
  "toolCallsOrder": [
    "get_temperature",
    "get_weather_condition",
    "get_humidity",
    "get_forecast"
  ]
}
```

**Behavior**:
- Uses Longest Common Subsequence (LCS) algorithm
- Allows partial matches (non-strict mode by default)
- Returns score from 0.0 to 1.0 based on order similarity

**Use Cases**:
- Validate critical operations happen in sequence
- Ensure dependencies are respected (e.g., auth before data fetch)
- Verify optimization patterns (e.g., caching checks before computation)

### 3. ToolCallArgsEvaluator

**Purpose**: Validates that tools are called with correct arguments.

**Configuration**: `evaluations/evaluators/tool-call-args.json`

**Example Usage**:
```json
"ToolCallArgsEvaluator": {
  "toolCalls": [
    {
      "name": "get_temperature",
      "args": {"city": "New York"}
    },
    {
      "name": "get_weather_condition",
      "args": {"city": "New York"}
    }
  ]
}
```

**Modes**:
- **Subset Mode** (default: `true`): Expected args must be present but can have additional args
- **Exact Mode** (`subset: false`): Args must match exactly

**Use Cases**:
- Validate correct parameters are passed
- Ensure data consistency across tool calls
- Verify input transformation logic

### 4. ToolCallOutputEvaluator

**Purpose**: Validates that tools produce expected outputs.

**Configuration**: `evaluations/evaluators/tool-call-output.json`

**Example Usage**:
```json
"ToolCallOutputEvaluator": {
  "toolOutputs": [
    {
      "name": "get_temperature",
      "output": "{'temperature': 25.0, 'unit': 'fahrenheit'}"
    },
    {
      "name": "get_forecast",
      "output": "{'forecast': 'Overcast with mild temperatures'}"
    }
  ]
}
```

**Behavior**:
- Compares output strings exactly
- Output must be JSON-serialized string
- Returns 1.0 for exact match, 0.0 otherwise
- **Note**: Current implementation uses single quotes for Python dict format

**Use Cases**:
- Validate tool output format
- Ensure deterministic tool behavior
- Verify data transformations

## Complete Example

### Test Case: "tokyo_forecast"

This test validates all aspects of tool usage for fetching Tokyo's weather forecast:

```json
{
  "id": "tokyo_forecast",
  "name": "Tokyo Weather Forecast",
  "inputs": {
    "city": "Tokyo",
    "action": "get_forecast"
  },
  "evaluationCriterias": {
    "ToolCallCountEvaluator": {
      "toolCallsCount": {
        "get_temperature": ["=", 1],
        "get_weather_condition": ["=", 1],
        "get_humidity": ["=", 1],
        "get_forecast": ["=", 1]
      }
    },
    "ToolCallOrderEvaluator": {
      "toolCallsOrder": [
        "get_temperature",
        "get_weather_condition",
        "get_humidity",
        "get_forecast"
      ]
    },
    "ToolCallArgsEvaluator": {
      "toolCalls": [
        {
          "name": "get_temperature",
          "args": {"city": "Tokyo"}
        },
        {
          "name": "get_weather_condition",
          "args": {"city": "Tokyo"}
        },
        {
          "name": "get_humidity",
          "args": {"city": "Tokyo"}
        },
        {
          "name": "get_forecast",
          "args": {"city": "Tokyo"}
        }
      ]
    },
    "ToolCallOutputEvaluator": {
      "toolOutputs": [
        {
          "name": "get_temperature",
          "output": "{'temperature': 25.0, 'unit': 'fahrenheit'}"
        },
        {
          "name": "get_weather_condition",
          "output": "{'condition': 'cloudy'}"
        },
        {
          "name": "get_humidity",
          "output": "{'humidity': 65}"
        },
        {
          "name": "get_forecast",
          "output": "{'forecast': 'Overcast with mild temperatures'}"
        }
      ]
    }
  }
}
```

### What This Validates

1. **Count**: Each tool is called exactly once ✓
2. **Order**: Tools are called in the correct sequence ✓
3. **Args**: All tools receive "Tokyo" as the city argument ✓
4. **Output**: All tools return the expected data ✓

## How Tool Calls Are Extracted

Tool calls are extracted from OpenTelemetry spans that have the `tool.name` attribute set. The weather_tools agent uses the `@mock_tool_span` decorator to ensure each tool invocation creates a span with:

- `tool.name`: The tool function name
- `input.value`: JSON-serialized tool arguments
- `output.value`: JSON-serialized tool output

### Current Implementation

The weather_tools sample uses direct async function calls (not LangChain tools) with the following decorator stack:

```python
@traced()                    # Creates OTEL span for tracing
@mockable(example_calls=...) # Provides mock data during evaluation
@mock_tool_span              # Sets tool.name attribute on span
async def get_temperature(city: str) -> dict:
    return {"content": {"temperature": 72.5, "unit": "fahrenheit"}}
```

### Content Wrapper Pattern

All tool outputs use a consistent `{"content": {...}}` structure:
- Tool outputs: `{"content": {"temperature": 72.5, "unit": "fahrenheit"}}`
- This ensures consistent serialization and makes data extraction predictable

## Running Evaluations

Execute all evaluators including tool call evaluators:

```bash
uv run uipath eval samples/weather_tools/main.py samples/weather_tools/evaluations/eval-sets/default.json --workers 1
```

## Test Cases in Default Eval Set

The `default.json` eval set includes 5 comprehensive test cases:

1. **basic_weather** - Tests 3 tool calls (temperature, condition, humidity)
2. **weather_with_forecast** - Tests 4 tool calls including forecast
3. **weather_with_alerts** - Tests 4 tool calls including alerts
4. **sunny_weather** - Tests sunny weather conditions
5. **tokyo_forecast** - Tests Tokyo-specific forecast sequence

Each test case validates:
- Correct tool call count
- Proper tool call order
- Accurate tool arguments
- Expected tool outputs

## Best Practices

### 1. Start with Order, Then Add Count
Begin with `ToolCallOrderEvaluator` to ensure correct sequencing, then add `ToolCallCountEvaluator` for precise counts.

### 2. Use Subset Mode for Args
Unless you need exact matching, keep `subset: true` in args evaluator to allow flexibility.

### 3. Selective Output Validation
Only validate outputs for critical tools - validating all outputs can be brittle.

### 4. Combine with Trajectory Evaluator
Use `TrajectoryEvaluator` for high-level behavior validation alongside specific tool evaluators.

### 5. Test Different Action Paths
Create separate test cases for different action types (get_weather, get_forecast, get_alerts) to validate all code paths.

### 6. Content Wrapper Consistency
Ensure all tool outputs follow the `{"content": {...}}` pattern for consistent evaluation.

## Troubleshooting

### Order Validation Failing

**Problem**: Order evaluator score is low

**Solutions**:
- Check if conditional tool calls are included in expected order
- Use trajectory evaluator to see actual execution sequence
- Consider if strict mode is appropriate for your use case

### Args Validation Failing

**Problem**: Args evaluator reports mismatches

**Solutions**:
- Verify argument names match exactly (case-sensitive)
- Check if subset mode is appropriate
- Ensure arguments are JSON-serializable

### Output Validation Failing

**Problem**: Output evaluator reports mismatches

**Solutions**:
- Ensure outputs are JSON-serialized strings
- Check for trailing whitespace or formatting differences
- Verify content wrapper structure is consistent
- Consider if output validation is too strict

### Content Wrapper Issues

**Problem**: Tool outputs don't match expected format

**Solutions**:
- Ensure all tools return `{"content": {...}}` structure
- Check that serialization is consistent across tools
- Verify that evaluator expectations match actual output format
