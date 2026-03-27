# Greeter Sample - Simulated Input Testing

This sample demonstrates LLM-based input generation (simulation) during evaluations and proper span instrumentation.

## Overview

The greeter function generates personalized greetings based on:
- **name**: The person's name
- **greeting_style**: The style of greeting (formal, casual, enthusiastic)

## Running the Function

```bash
# From the greeter directory
uv run uipath run main '{"name": "Alice", "greeting_style": "formal"}'
```

**Expected output:**
```json
{
  "message": "Good day, Alice. It is a pleasure to meet you.",
  "recipient": "Alice",
  "style": "formal"
}
```

## Running Evaluations

### Option 1: Basic Evaluation (No Authentication Required)

Test the function with predefined inputs - no LLM calls needed:

```bash
uv run uipath eval main ./evaluations/eval-sets/basic.json --output-file output-basic.json
```

This will run 3 test cases with fixed inputs and verify the outputs match expected results.

### Option 2: Simulated Input Evaluation (Requires Authentication)

The `simulated-input.json` eval set demonstrates LLM-based input generation:

```bash
# First, authenticate with UiPath
uipath auth

# Or set environment variables
export UIPATH_URL=https://your-tenant.uipath.com
export UIPATH_ACCESS_TOKEN=your-token

# Then run the simulation eval
uv run uipath eval main ./evaluations/eval-sets/simulated-input.json --output-file output.json
```

### How Simulated Input Works

Each evaluation in `simulated-input.json` has:
- `"inputs": {}` - Empty inputs
- `"inputMockingStrategy"` - Configuration for LLM-based input generation with a prompt

The evaluation framework will:
1. Extract the function's input schema from the dataclass (`GreeterInput`)
2. Call an LLM with the generation prompt and schema
3. Parse the LLM's response to generate valid inputs
4. Execute the function with the generated inputs
5. Evaluate the output against expected results

### Observability - "Simulate Input" Span

When running evals with input simulation, you'll see a **"Simulate Input"** span in the traces with these attributes:

**Custom attributes:**
- `span_type`: `"simulatedInput"`
- `type`: `"simulatedInput"`
- `uipath.custom_instrumentation`: `true`

**Standard @traced attributes:**
- `input.mime_type`: `"application/json"`
- `input.value`: JSON with `mocking_strategy`, `input_schema`, `expected_behavior`, `expected_output`
- `output.mime_type`: `"application/json"`
- `output.value`: The generated input (LLM response)

This span matches the pattern used in the uipath-agents-python repository.
