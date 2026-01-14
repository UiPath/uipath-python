---
allowed-tools: Read, Write, Bash, Glob, Grep, Edit
description: Create a new integration test case following the testcases/ pattern
argument-hint: <test-name> <description>
---

I'll help you create a new integration test case following the established pattern in the `testcases/` directory, similar to the `eval-input-overrides` example from PR #1101.

## Understanding the Test Structure

Based on the existing test pattern, each integration test should have:
- `run.sh` - Main test execution script
- `pyproject.toml` - Python dependencies
- `entry-points.json` - Entry point configuration
- `uipath.json` - UiPath configuration
- `src/` directory containing:
  - Evaluation set JSON files
  - Input/configuration JSON files
  - `assert.py` - Validation script

## Step 1: Gather Information

I need to understand what you're testing. Please provide:
1. **Test Name**: A descriptive name for your test (e.g., "eval-multimodal-inputs")
2. **Test Purpose**: What feature or scenario are you testing?
3. **Evaluation Set**: What evaluations will run?
4. **Expected Behavior**: What should the test verify?

Let me check the existing testcases structure:

!ls -1 testcases/

## Step 2: Create Test Directory Structure

Based on your test name `${test-name}`, I'll create:

```bash
testcases/${test-name}/
├── run.sh
├── pyproject.toml
├── entry-points.json
├── uipath.json
├── src/
│   ├── eval-set.json
│   ├── config.json (if needed)
│   └── assert.py
```

Let me read the reference implementation to understand the pattern:

!cat testcases/eval-input-overrides/run.sh
!cat testcases/eval-input-overrides/pyproject.toml
!cat testcases/eval-input-overrides/src/assert.py

## Step 3: Create the Test Files

I'll create each file following the established pattern:

### 1. run.sh - Test Execution Script
```bash
#!/bin/bash
set -e

echo "Syncing dependencies..."
uv sync

echo ""
echo "Running ${test-name} integration test..."
echo ""

# Create output directory
mkdir -p __uipath

# Run evaluations
uv run uipath eval main src/eval-set.json \
  --no-report \
  --output-file __uipath/output.json

echo ""
echo "Test completed! Verifying results..."
echo ""

# Run assertion script to verify results
uv run python src/assert.py

echo ""
echo "✅ ${test-name} integration test completed successfully!"
```

### 2. pyproject.toml - Dependencies
```toml
[project]
name = "${test-name}"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "uipath>=2.4.0",
]

[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"
```

### 3. entry-points.json - Entry Points Configuration
```json
{
  "main": "src/main.json"
}
```

### 4. uipath.json - UiPath Configuration
```json
{
  "name": "${test-name}",
  "version": "1.0.0"
}
```

### 5. src/eval-set.json - Evaluation Set
(You'll need to provide the specific evaluation configuration)

### 6. src/assert.py - Validation Script
```python
"""Assertions for ${test-name} testcase."""
import json
import os


def main() -> None:
    """Main assertion logic."""
    output_file = "__uipath/output.json"

    assert os.path.isfile(output_file), (
        f"Evaluation output file '{output_file}' not found"
    )
    print(f"✓ Found evaluation output file: {output_file}")

    with open(output_file, "r", encoding="utf-8") as f:
        output_data = json.load(f)

    print("✓ Loaded evaluation output")

    # Add your specific assertions here
    assert "evaluationSetResults" in output_data

    evaluation_results = output_data["evaluationSetResults"]
    assert len(evaluation_results) > 0, "No evaluation results found"

    print(f"✓ Found {len(evaluation_results)} evaluation result(s)")

    # Add test-specific validations

    print("\\n✅ All assertions passed!")


if __name__ == "__main__":
    main()
```

## Step 4: Make run.sh Executable

!chmod +x testcases/${test-name}/run.sh

## Step 5: Test the Integration Test

Let's validate the test runs correctly:

!cd testcases/${test-name} && ./run.sh

## Step 6: Add to Documentation

Consider documenting your test in the project README or test documentation:
- What scenario it tests
- How to run it manually
- What it validates

---

## Summary

Your new integration test `${test-name}` has been created following the established pattern:

✅ **Directory Structure**: Matches testcases/ pattern
✅ **Dependencies**: Configured in pyproject.toml
✅ **Test Script**: run.sh with proper error handling
✅ **Assertions**: Validation logic in assert.py
✅ **Configuration**: UiPath and entry points configured

## Next Steps

1. **Customize** the eval-set.json with your specific test data
2. **Update** assert.py with test-specific validations
3. **Run** the test: `cd testcases/${test-name} && ./run.sh`
4. **Document** the test purpose and usage
5. **Commit** the new test to version control

## Tips

- Keep tests focused on a single feature or scenario
- Use descriptive evaluation names in eval-set.json
- Add clear assertion messages for debugging
- Follow the echo statement pattern (removed from initial header, kept for progress)
- Ensure all JSON files are properly formatted

Need help customizing any specific part of the test? Just ask!
