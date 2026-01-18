---
description: Create evaluation test cases for UiPath agents
allowed-tools: Bash, Read, Write, Glob, AskUserQuestion
argument-hint: [eval-name]
contextAware: true
autoDetect: true
---

# Create Evaluation Test Cases

Design comprehensive test cases for your UiPath agents with expected input/output pairs.

## Workflow

### Step 1: Project Verification
I'll verify that:
- Your project exists (`uipath.json`)
- At least one agent is defined (`entry-points.json`)

If missing, create an agent first with `/create-agent`.

### Step 2: Evaluation Details
I'll ask you for:
- **Evaluation Set Name** - Identifier for this test suite (e.g., "calculator-basic-ops")
- **Description** - What scenarios this evaluation covers
- **Target Agent** - Which agent to evaluate (if multiple)
- **Number of Test Cases** - How many tests to create

### Step 3: Test Case Collection
For each test case, I'll guide you through:

**Input Collection:**
Based on the agent's input schema, I'll prompt for each field with validation:
```
Test Case 1: Basic Addition
Enter a (number) - First operand: 10
Enter b (number) - Second operand: 5
Select operator (string) - Operation type:
  1. +
  2. -
  3. *
  4. /
Choice: 1
```

**Expected Output:**
```
Enter expected result (number): 15
```

**Test Metadata:**
```
Test case ID (auto-generated): test-1-addition
Test description (optional): Add two positive numbers
```

### Step 4: Smart Test Generation (Optional)
I can generate realistic test cases automatically by analyzing your agent:
- **Happy Path**: Normal operations with typical inputs
- **Edge Cases**: Boundary conditions and limits
- **Error Scenarios**: Invalid inputs and error handling
- **Comprehensive Coverage**: Multiple scenarios per function

### Step 5: File Generation
I'll create:
```
evaluations/<eval-name>.json
```

With structure:
```json
{
  "evaluationSetName": "calculator-basic-operations",
  "evaluationSetDescription": "Test basic arithmetic operations",
  "evaluations": [
    {
      "evaluationId": "test-1-addition",
      "input": {"a": 10, "b": 5, "operator": "+"},
      "expectedOutput": {"result": 15},
      "evaluators": ["default"]
    }
  ]
}
```

### Step 6: Validation
I'll validate that:
- Input schemas match agent's input definition
- Output schemas match agent's output definition
- All required fields are provided
- Data types are correct

## Test Case Types

**Happy Path Tests:**
- Normal operations with typical valid inputs
- Expected successful outcomes
- Standard use cases

**Edge Case Tests:**
- Boundary values (0, min, max)
- Empty/null values
- Large datasets
- Special characters

**Error Scenario Tests:**
- Invalid input types
- Missing required fields
- Out-of-range values
- Expected error messages

## Generated File Structure

```
evaluations/
├── calculator-basic-operations.json
├── calculator-edge-cases.json
└── data-processor-scenarios.json
```

Each file contains multiple test cases organized by purpose.

## Next Steps

After creating evaluations:
- **Run Tests**: Use `/run-eval` to execute test cases
- **View Results**: See pass/fail status and metrics
- **Create More**: Add additional evaluation sets
- **Analyze**: Review failing tests and improve agent

## Schema Validation

The created evaluation JSON is automatically validated against:
- Agent's input JSON schema from `entry-points.json`
- Agent's output JSON schema from `entry-points.json`
- Required field constraints
- Type compatibility

This ensures your tests are compatible with your agent's interface.

Ready to create comprehensive test coverage for your agent!
