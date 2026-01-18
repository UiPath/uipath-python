---
description: List all agents and evaluations in the current UiPath project
allowed-tools: Read, Glob, Bash
argument-hint:
contextAware: true
autoDetect: true
---

# List Project Resources

View all agents and evaluations in your UiPath project with detailed schema information.

## Workflow

### Step 1: Project Detection
I'll check for:
- `uipath.json` - Project configuration
- `entry-points.json` - Agent entry points and schemas
- `evaluations/` directory - Test sets
- `testcases/` directory - Integration tests

### Step 2: Agent Listing
If agents found, I'll display:

```
AGENTS
═════════════════════════════════════════════════════════════════

1. calculator (from: main.py:main)
   ├─ INPUTS:
   │  ├─ a: number [required]
   │  │  └─ Description: First operand
   │  ├─ b: number [required]
   │  │  └─ Description: Second operand
   │  └─ operator: string [required, enum]
   │     ├─ Description: Math operator
   │     └─ Allowed: ["+", "-", "*", "/"]
   │
   └─ OUTPUTS:
      └─ result: number
         └─ Description: Calculation result

2. data-processor (from: processor.py:process)
   ├─ INPUTS:
   │  ├─ data: string [required]
   │  ├─ format: string [required, enum]
   │  │  └─ Allowed: ["json", "csv", "excel"]
   │  └─ filter_empty: boolean [optional]
   │
   └─ OUTPUTS:
      ├─ output: string
      └─ metadata: object

3. email-sender (from: email.py:send)
   └─ [Similar format...]
```

### Step 3: Evaluation Listing
I'll discover and list all test files:

```
EVALUATIONS
═════════════════════════════════════════════════════════════════

1. evaluations/calculator-basic-operations.json
   ├─ Test Cases: 3
   ├─ Target Agent: calculator
   ├─ Status: Not run
   ├─ Last Modified: 2 hours ago
   └─ Size: 1.2 KB

2. evaluations/calculator-edge-cases.json
   ├─ Test Cases: 5
   ├─ Target Agent: calculator
   ├─ Status: ✅ Last run passed (3/5)
   ├─ Last Run: 30 minutes ago
   └─ Size: 2.1 KB

3. testcases/data-processor/default.json
   ├─ Test Cases: 8
   ├─ Target Agent: data-processor
   ├─ Status: ✅ All tests passed
   ├─ Last Run: 1 day ago
   └─ Size: 4.3 KB
```

### Step 4: Project Summary
Summary statistics:

```
PROJECT SUMMARY
═════════════════════════════════════════════════════════════════

Project Name:          my-uipath-project
Location:              /Users/akshaya/projects/my-project
Total Agents:          3
Total Input Fields:    12
Total Output Fields:   8
Evaluation Sets:       3
Total Test Cases:      16

AGENT STATUS:
├─ calculator:        ✅ (1 input, 1 output)
├─ data-processor:    ✅ (3 inputs, 2 outputs)
└─ email-sender:      ✅ (3 inputs, 2 outputs)

EVALUATION STATUS:
├─ calculator-basic-operations:     Not run
├─ calculator-edge-cases:           ✅ 3/5 passed (60%)
└─ data-processor-scenarios:        ✅ 8/8 passed (100%)
```

## Detailed Schema Information

For each agent, I show:

**Input Fields:**
- Field name and type
- Required status
- Default value (if any)
- Description
- Constraints (min, max, enum values, pattern, etc.)
- Examples

**Output Fields:**
- Field name and type
- Description
- Example output value

## Evaluation Metadata

For each evaluation set, I display:

**Test Information:**
- Number of test cases
- Target agent
- Test IDs and descriptions

**Execution History:**
- Last run timestamp
- Pass/fail statistics
- Average execution time

**File Details:**
- File path
- File size
- Last modified date

## Quick Actions

Access commands directly from the listing:

```
QUICK ACTIONS
═════════════════════════════════════════════════════════════════

Agents:
  /run-agent calculator              → Run calculator agent
  /run-agent data-processor          → Run data-processor agent
  /create-eval calculator-tests      → Create tests for calculator

Evaluations:
  /run-eval calculator-edge-cases    → Run calculator edge case tests
  /run-eval data-processor           → Run data-processor tests
  /create-eval more-calculator-tests → Add more tests
```

## Use Cases

**New to Project?**
- Use `/list` to see what's available
- Use `/run-agent` to test an agent
- Use `/run-eval` to see test results

**Debugging Failures?**
- Use `/list` to check agent schemas
- Use `/run-agent` to test with specific inputs
- Check evaluation results to find failing cases

**Adding Tests?**
- Use `/list` to see existing evaluations
- Use `/create-eval` to add more comprehensive tests
- Use `/run-eval` to validate

## Information Density

I'll adapt the detail level:
- **Quick View**: Just agent/eval names
- **Summary View**: Names + input/output count
- **Detailed View**: Full schemas with examples
- **Analysis View**: Statistics and recommendations

No project found? Create your first agent with `/create-agent`!
