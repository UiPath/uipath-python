---
description: Run evaluations for UiPath agents
allowed-tools: Bash, Read, Glob, AskUserQuestion
argument-hint: [eval-file]
contextAware: true
autoDetect: true
---

# Run Evaluations

Execute and analyze evaluation test cases for your UiPath agents.

## Workflow

### Step 1: Project Verification
I'll verify your project has:
- `uipath.json` - Project configuration
- `entry-points.json` - Agent definitions
- Evaluation files in `evaluations/` or `testcases/`

If missing, create an agent with `/create-agent` and tests with `/create-eval`.

### Step 2: Evaluation Discovery
I'll scan for evaluation test files:
- `evaluations/*.json` - User-created test sets
- `testcases/*/src/*.json` - Integration test cases

Display format:
```
AVAILABLE EVALUATIONS
═════════════════════════════════════════════════════════

1. evaluations/calculator-basic-operations.json
   └─ Agent: calculator | Tests: 3 | Last run: 2 hours ago

2. evaluations/calculator-edge-cases.json
   └─ Agent: calculator | Tests: 5 | Last run: Never

3. testcases/data-processor/default.json
   └─ Agent: data-processor | Tests: 8 | Last run: 1 day ago
```

### Step 3: Evaluation Selection
If multiple test sets exist, I'll prompt you to select one. Single eval files auto-select.

### Step 4: Execution Configuration
I'll ask for:
- **Number of Workers** - Parallel test execution (1-8, default: 1)
- **Enable Mocker Cache** - Cache LLM responses for reproducibility
- **Report to Studio** - Send results to UiPath Cloud (optional)

Example:
```
Parallel workers (1-8) [default: 1]: 4
Enable mocker cache? (y/n) [default: n]: y
Report to Studio? (y/n) [default: n]: n
```

### Step 5: Evaluation Execution
I'll run:
```bash
uipath eval <entrypoint> <eval-file> \
  --workers 4 \
  --no-report \
  --output-file eval-results.json
```

Real-time progress indicator shows test execution status.

### Step 6: Results Analysis

Results displayed in formatted table:

```
EVALUATION RESULTS
═════════════════════════════════════════════════════════════════════

Test ID         Status  Evaluator  Score   Time    Error
─────────────────────────────────────────────────────────────────────
test-1-addition  ✅ PASS default    1.0     0.45s
test-2-subtract  ✅ PASS default    1.0     0.38s
test-3-multiply  ⚠️ WARN default    0.75    0.52s   Precision loss
test-4-divide-0  ❌ FAIL default    0.0     0.41s   Output mismatch
test-5-complex   ✅ PASS default    1.0     0.39s

SUMMARY METRICS
═════════════════════════════════════════════════════════════════════
Total Tests:        5
Passed:             4 (80%)
Warnings:           1 (20%)
Failed:             0 (0%)
Average Score:      0.95
Total Execution:    2.15 seconds
Pass Rate:          80%
```

### Step 7: Detailed Failure Analysis

For any failed or warning tests, I'll show detailed diagnostics:

**Test: test-4-divide-0 (FAILED)**
```
Status:           ❌ FAILED
Execution Time:   0.41s
Evaluator:        default

Input:
  a: 10
  b: 0
  operator: "/"

Expected Output:
  result: "error"

Actual Output:
  result: null

Difference:
  - Expected: {"result": "error"}
  - Got:      {"result": null}
  - Issue: Output type mismatch (string vs null)
```

I'll provide suggestions:
- Add input validation for edge cases (division by zero)
- Implement proper error handling
- Return meaningful error messages

### Step 8: Follow-up Actions

After evaluation, you can:
- **View Details** - Detailed breakdown of each test
- **Fix Issues** - I can help modify agent code
- **Re-run Tests** - Execute again with different config
- **Create More Tests** - Add additional test cases
- **Export Results** - Save results to JSON file
- **Compare Runs** - See improvements over time

## Test Coverage Analysis

I'll analyze your test coverage:
- **Input Space Coverage** - Which input combinations are tested
- **Output Validation** - Coverage of different output scenarios
- **Edge Cases** - Boundary conditions and error paths
- **Recommendations** - Suggest additional test cases

## Performance Metrics

Tracked metrics include:
- **Execution Time** - Per-test and total duration
- **Pass Rate** - Percentage of successful tests
- **Score Distribution** - Evaluator scores across tests
- **Performance Trends** - Improvements over multiple runs

## Integration with UiPath Cloud

Results can be:
- Reported to UiPath Cloud for monitoring
- Integrated with CI/CD pipelines
- Compared with previous runs
- Used for performance tracking

Create test cases with `/create-eval` and analyze results here!
