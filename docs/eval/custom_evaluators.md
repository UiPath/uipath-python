# Custom Python Evaluators

Custom Python Evaluators enable you to implement domain-specific evaluation logic tailored to your agent's unique requirements. When the built-in evaluators don't cover your specific use case, you can create custom evaluators with full control over the evaluation criteria and scoring logic.

## Overview

**Use Cases**:

- Domain-specific validation (e.g., healthcare data compliance, financial calculations)
- Complex multi-step verification logic
- Custom data extraction and comparison from tool calls
- Specialized scoring algorithms (e.g., Jaccard similarity, Levenshtein distance)
- Integration with external validation systems

**Returns**: Any `EvaluationResult` type (`NumericEvaluationResult`, `BooleanEvaluationResult`, or `ErrorEvaluationResult`)

## Project Structure

Custom evaluators must follow this directory structure:

```
your-project/
├── evals/
│   ├── evaluators/
│   │   ├── custom/
│   │   │   ├── your_evaluator.py       # Your evaluator implementation
│   │   │   ├── another_evaluator.py    # Additional custom evaluators
│   │   │   └── types/                  # Auto-generated type schemas
│   │   │       ├── your-evaluator-types.json
│   │   │       └── another-evaluator-types.json
│   │   ├── your-evaluator.json         # Auto-generated evaluator config
│   │   └── another-evaluator.json
│   └── eval_sets/
│       └── your_eval_set.json
└── ...
```

!!! important "Required Structure"
    - Custom evaluator files **must** be placed in `evals/evaluators/custom/` directory
    - Each file should contain one or more evaluator classes inheriting from `BaseEvaluator`
    - The directory structure is enforced by the CLI tooling

## Creating a Custom Evaluator

### Step 1: Generate Template

Use the CLI to create a new evaluator template:

```bash
uipath add evaluator my-custom-evaluator
```

This creates `evals/evaluators/custom/my_custom_evaluator.py` with a template structure.

### Step 2: Implement Evaluation Logic

A custom evaluator consists of three main components:

#### 1. Evaluation Criteria Class

Define the criteria that will be used to evaluate agent executions. This should contain only test-specific data like expected outputs:

```python
from pydantic import Field
from uipath.eval.evaluators import BaseEvaluationCriteria

class MyEvaluationCriteria(BaseEvaluationCriteria):
    """Criteria for my custom evaluator."""

    expected_values: list[str] = Field(default_factory=list)
```

#### 2. Evaluator Configuration Class

Define configuration options for your evaluator. This should contain behavioral settings like thresholds, modes, etc.:

```python
from uipath.eval.evaluators import BaseEvaluatorConfig

class MyEvaluatorConfig(BaseEvaluatorConfig[MyEvaluationCriteria]):
    """Configuration for my custom evaluator."""

    name: str = "MyCustomEvaluator"
    threshold: float = 0.8  # Minimum score to consider passing
    case_sensitive: bool = False  # Whether comparison is case-sensitive
    # Optional: set default criteria
    # default_evaluation_criteria: MyEvaluationCriteria | None = None
```

#### 3. Evaluator Implementation Class

Implement the core evaluation logic:

```python
from typing import List
from uipath.eval.evaluators import BaseEvaluator
from uipath.eval.models import AgentExecution, NumericEvaluationResult
import json

class MyCustomEvaluator(
    BaseEvaluator[MyEvaluationCriteria, MyEvaluatorConfig, str]
):
    """Custom evaluator with domain-specific logic.

    This evaluator performs custom validation on agent outputs
    by comparing extracted data against expected values.
    """

    async def evaluate(
        self,
        agent_execution: AgentExecution,
        evaluation_criteria: MyEvaluationCriteria
    ) -> NumericEvaluationResult:
        """Evaluate the agent execution against criteria.

        Args:
            agent_execution: The agent execution containing:
                - agent_input: Input received by the agent
                - agent_output: Output produced by the agent
                - agent_trace: OpenTelemetry spans with execution trace
                - simulation_instructions: Simulation instructions
            evaluation_criteria: Criteria to evaluate against

        Returns:
            EvaluationResult with score and details
        """
        # Extract data from agent execution
        actual_values = self._extract_values(agent_execution)
        expected_values = evaluation_criteria.expected_values

        # Apply case sensitivity from config
        if not self.evaluator_config.case_sensitive:
            actual_values = [v.lower() for v in actual_values]
            expected_values = [v.lower() for v in expected_values]

        # Compute score
        score = self._compute_similarity(actual_values, expected_values)

        # Check against threshold from config
        passed = score >= self.evaluator_config.threshold

        return NumericEvaluationResult(
            score=score,
            details=json.dumps({
                "expected": expected_values,
                "actual": actual_values,
                "threshold": self.evaluator_config.threshold,
                "passed": passed,
                "case_sensitive": self.evaluator_config.case_sensitive,
            }),
        )

    def _extract_values(self, agent_execution: AgentExecution) -> List[str]:
        """Extract values from agent execution (implement your logic)."""
        # Your custom extraction logic here
        return []

    def _compute_similarity(
        self, actual: List[str], expected: List[str]
    ) -> float:
        """Compute similarity score (implement your logic)."""
        # Your custom scoring logic here
        return 0.0

    @classmethod
    def get_evaluator_id(cls) -> str:
        """Get the unique evaluator identifier.

        Returns:
            The evaluator ID (must be unique across all evaluators)
        """
        return "MyCustomEvaluator"
```

### Step 3: Register the Evaluator

Register your evaluator to generate the configuration files:

```bash
uipath register evaluator my_custom_evaluator.py
```

This command:

1. Validates your evaluator implementation
2. Generates `evals/evaluators/custom/types/my-custom-evaluator-types.json` with type schemas
3. Creates `evals/evaluators/my-custom-evaluator.json` with evaluator configuration

The generated configuration file will contain:

```json
{
  "version": "1.0",
  "id": "MyCustomEvaluator",
  "evaluatorTypeId": "file://types/my-custom-evaluator-types.json",
  "evaluatorSchema": "file://my_custom_evaluator.py:MyCustomEvaluator",
  "description": "Custom evaluator with domain-specific logic...",
  "evaluatorConfig": {
    "name": "MyCustomEvaluator",
    "threshold": 0.8,
    "caseSensitive": false
  }
}
```

!!! note "Evaluator Schema Format"
    - `evaluatorTypeId`: Format is `file://types/<kebab-case-name>-types.json` - points to the generated type schema
    - `evaluatorSchema`: Format is `file://<filename>.py:<ClassName>` - tells the runtime where to load your custom evaluator class from

    The `file://` prefix indicates these are local file references that will be resolved relative to the `evals/evaluators/custom/` directory.

### Step 4: Use in Evaluation Sets

Reference your custom evaluator in evaluation sets:

```json
{
  "version": "1.0",
  "id": "my-eval-set",
  "evaluatorRefs": ["MyCustomEvaluator"],
  "evaluationItems": [
    {
      "id": "test-1",
      "agentInput": {"query": "Process data"},
      "evaluations": [
        {
          "evaluatorId": "MyCustomEvaluator",
          "evaluationCriteria": {
            "expectedValues": ["value1", "value2"]
          }
        }
      ]
    }
  ]
}
```

!!! note "Criteria vs Config"
    - **evaluationCriteria**: Test-specific data (e.g., `expectedValues`) - varies per test case
    - **evaluatorConfig**: Behavioral settings (e.g., `threshold`, `caseSensitive`) - set once in the evaluator JSON file

## Working with Agent Traces

Custom evaluators often need to extract information from tool calls in the agent execution trace. The SDK provides helper functions for common operations.

### Extracting Tool Calls

```python
from uipath.eval._helpers.evaluators_helpers import extract_tool_calls

def _process_tool_calls(self, agent_execution: AgentExecution) -> List[str]:
    """Extract and process tool calls from the execution trace."""
    tool_calls = extract_tool_calls(agent_execution.agent_trace)

    results = []
    for tool_call in tool_calls:
        # Access tool name
        tool_name = tool_call.name

        # Access tool arguments
        args = tool_call.args or {}

        if tool_name == "SpecificTool":
            # Extract specific data from arguments
            data = args.get("parameter_name", "")
            results.append(data)

    return results
```

### Available Helper Functions

```python
from uipath.eval._helpers.evaluators_helpers import (
    extract_tool_calls,          # Extract tool calls with arguments
    extract_tool_calls_names,     # Extract just tool names
    extract_tool_calls_outputs,   # Extract tool outputs
    trace_to_str,                 # Convert trace to string representation
)
```

## Complete Example

Here's a complete example based on real-world usage that compares data patterns using Jaccard similarity:

```python
"""Custom evaluator for pattern comparison."""
import json
from typing import List

from pydantic import Field
from uipath.eval.evaluators import BaseEvaluator
from uipath.eval.evaluators.base_evaluator import (
    BaseEvaluationCriteria,
    BaseEvaluatorConfig,
)
from uipath.eval.models import EvaluationResult, NumericEvaluationResult
from uipath.eval.models import AgentExecution
from uipath.eval._helpers.evaluators_helpers import extract_tool_calls


def _compute_jaccard_similarity(expected: List[str], actual: List[str]) -> float:
    """Compute Jaccard similarity (intersection over union).

    Returns 1.0 when both expected and actual are empty (perfect match).
    """
    expected_set = set(expected) if expected else set()
    actual_set = set(actual) if actual else set()

    # If both are empty, that's a perfect match
    if len(expected_set) == 0 and len(actual_set) == 0:
        return 1.0

    intersection = len(expected_set.intersection(actual_set))
    union = len(expected_set.union(actual_set))
    return intersection / union if union > 0 else 0.0


class PatternEvaluatorCriteria(BaseEvaluationCriteria):
    """Evaluation criteria for pattern evaluator."""

    expected_output: List[str] = Field(default_factory=list)


class PatternEvaluatorConfig(BaseEvaluatorConfig[PatternEvaluatorCriteria]):
    """Configuration for pattern evaluator."""

    name: str = "PatternComparisonEvaluator"


class PatternComparisonEvaluator(
    BaseEvaluator[PatternEvaluatorCriteria, PatternEvaluatorConfig, str]
):
    """Custom evaluator for pattern comparison.

    Extends BaseEvaluator to extract data from specific tool calls and
    validates patterns found against expected patterns using Jaccard
    similarity (intersection over union).
    """

    async def evaluate(
        self,
        agent_execution: AgentExecution,
        evaluation_criteria: PatternEvaluatorCriteria
    ) -> EvaluationResult:
        """Evaluate the pattern comparison.

        Args:
            agent_execution: The agent execution containing trace data
            evaluation_criteria: Expected output patterns

        Returns:
            EvaluationResult with score (0.0 to 1.0) based on Jaccard similarity
        """
        expected_output = evaluation_criteria.expected_output

        # Extract actual output from tool calls
        actual_output = self._extract_patterns(agent_execution)

        # Compute score using intersection over union
        score = _compute_jaccard_similarity(expected_output, actual_output)

        return NumericEvaluationResult(
            score=score,
            details=json.dumps({
                "expected_patterns": expected_output,
                "actual_patterns": actual_output,
                "matching_count": len(set(expected_output).intersection(set(actual_output))),
                "expected_count": len(expected_output),
                "actual_count": len(actual_output),
            }),
        )

    def _extract_patterns(self, agent_execution: AgentExecution) -> List[str]:
        """Extract patterns from tool calls.

        Args:
            agent_execution: The agent execution containing trace data

        Returns:
            List of pattern strings found
        """
        # Extract tool calls with arguments using the helper function
        tool_calls = extract_tool_calls(agent_execution.agent_trace)

        for tool_call in tool_calls:
            if tool_call.name == "DataProcessingTool":
                args = tool_call.args or {}
                file_name = str(args.get("FileName", ""))
                if file_name.startswith("PatternData"):
                    input_data = str(args.get("InputData", ""))
                    if input_data:
                        lines = input_data.split("\n")
                        # Extract and process patterns (custom logic)
                        patterns = [line.strip() for line in lines[1:] if line.strip()]
                        return patterns

        return []

    @classmethod
    def get_evaluator_id(cls) -> str:
        """Get the evaluator type ID.

        Returns:
            The evaluator type identifier
        """
        return "PatternComparisonEvaluator"
```

## Best Practices

### 1. Type Annotations and Documentation

Always include complete type annotations and Google-style docstrings:

```python
def _extract_data(
    self,
    agent_execution: AgentExecution,
    tool_name: str
) -> List[str]:
    """Extract data from specific tool calls.

    Args:
        agent_execution: The agent execution to process
        tool_name: The name of the tool to extract data from

    Returns:
        List of extracted data strings

    Raises:
        ValueError: If the tool call format is invalid
    """
    # Implementation
```

### 2. Error Handling

Use proper error handling and return meaningful results:

```python
from uipath.eval.models import ErrorEvaluationResult

async def evaluate(
    self,
    agent_execution: AgentExecution,
    evaluation_criteria: MyCriteria
) -> EvaluationResult:
    """Evaluate with error handling."""
    try:
        # Your evaluation logic
        score = self._compute_score(agent_execution)
        return NumericEvaluationResult(score=score)
    except Exception as e:
        return ErrorEvaluationResult(
            error=f"Evaluation failed: {str(e)}"
        )
```

### 3. Reusable Helper Methods

Extract common logic into reusable helper methods:

```python
def _extract_from_tool(
    self,
    agent_execution: AgentExecution,
    tool_name: str,
    parameter_name: str
) -> str:
    """Reusable method to extract parameter from tool calls."""
    tool_calls = extract_tool_calls(agent_execution.agent_trace)
    for tool_call in tool_calls:
        if tool_call.name == tool_name:
            args = tool_call.args or {}
            return str(args.get(parameter_name, ""))
    return ""
```

### 4. Clear Scoring Logic

Make your scoring logic explicit and well-documented, using config values appropriately:

```python
def _compute_score(
    self,
    actual: List[str],
    expected: List[str]
) -> float:
    """Compute evaluation score.

    Scoring algorithm:
    - 1.0: Perfect match (all expected items found)
    - 0.5-0.99: Partial match (some items found)
    - 0.0: No match (no items found)

    Uses the case_sensitive setting from evaluator config.

    Args:
        actual: Actual values extracted from execution
        expected: Expected values from criteria

    Returns:
        Score between 0.0 and 1.0
    """
    if not expected:
        return 1.0 if not actual else 0.0

    # Apply case sensitivity from config
    if not self.evaluator_config.case_sensitive:
        actual = [v.lower() for v in actual]
        expected = [v.lower() for v in expected]

    matches = len(set(actual).intersection(set(expected)))
    return matches / len(expected)
```

### 5. Detailed Results

Provide detailed information in evaluation results, including config values that were actually used:

```python
# Calculate what we need for details
passed = score >= self.evaluator_config.threshold

return NumericEvaluationResult(
    score=score,
    details=json.dumps({
        "expected": expected_values,
        "actual": actual_values,
        "matches": matching_items,
        "missing": missing_items,
        "extra": extra_items,
        "algorithm": "jaccard_similarity",
        "threshold": self.evaluator_config.threshold,
        "passed": passed,
        "case_sensitive": self.evaluator_config.case_sensitive,
    }),
)
```

## Generic Type Parameters

Custom evaluators use three generic type parameters in the class signature:

```python
class MyEvaluator(BaseEvaluator[T, C, J]):
    """
    T: Evaluation criteria type (subclass of BaseEvaluationCriteria)
    C: Configuration type (subclass of BaseEvaluatorConfig[T])
    J: Justification type (str, None, or BaseEvaluatorJustification)
    """
```

**Common patterns**:

- `BaseEvaluator[MyCriteria, MyConfig, str]` - Returns string justification
- `BaseEvaluator[MyCriteria, MyConfig, type(None)]` - No justification (score only)
- `BaseEvaluator[MyCriteria, MyConfig, MyJustification]` - Structured justification

## Testing Custom Evaluators

Test your evaluators locally before registration:

```python
import pytest
from uipath.eval.models import AgentExecution

@pytest.mark.asyncio
async def test_custom_evaluator() -> None:
    """Test custom evaluator logic."""
    # Create test data
    agent_execution = AgentExecution(
        agent_input={"query": "test"},
        agent_output={"result": "test output"},
        agent_trace=[],
    )

    # Create evaluator with config
    evaluator = MyCustomEvaluator(
        id="test-evaluator",
        config={
            "name": "MyCustomEvaluator",
            "threshold": 0.8,
            "case_sensitive": False,
        }
    )

    # Evaluate with criteria
    criteria = MyEvaluationCriteria(expected_values=["value1"])
    result = await evaluator.evaluate(agent_execution, criteria)

    # Assert
    assert result.score >= 0.0
    assert result.score <= 1.0
```

## Common Patterns

### Pattern 1: Extracting Data from Specific Tools

```python
def _extract_from_specific_tool(
    self, agent_execution: AgentExecution
) -> str:
    """Extract data from a specific tool call."""
    tool_calls = extract_tool_calls(agent_execution.agent_trace)

    for tool_call in tool_calls:
        if tool_call.name == "TargetTool":
            args = tool_call.args or {}
            return str(args.get("target_parameter", ""))

    return ""
```

### Pattern 2: Computing Set-Based Similarity

```python
def _compute_set_similarity(
    self, actual: List[str], expected: List[str]
) -> float:
    """Compute similarity using set operations."""
    actual_set = set(actual)
    expected_set = set(expected)

    if not expected_set:
        return 1.0 if not actual_set else 0.0

    intersection = len(actual_set.intersection(expected_set))
    return intersection / len(expected_set)
```

### Pattern 3: Multi-Step Validation

```python
async def evaluate(
    self,
    agent_execution: AgentExecution,
    evaluation_criteria: MyCriteria
) -> EvaluationResult:
    """Multi-step validation using config settings."""
    # Step 1: Validate structure (use strict mode from config)
    if not self._validate_structure(agent_execution, self.evaluator_config.strict):
        return NumericEvaluationResult(
            score=0.0,
            details=json.dumps({
                "error": "Invalid structure",
                "strict_mode": self.evaluator_config.strict,
            })
        )

    # Step 2: Extract data
    data = self._extract_data(agent_execution)

    # Step 3: Compare and score
    score = self._compare_data(data, evaluation_criteria.expected_data)

    # Step 4: Check against threshold from config
    passed = score >= self.evaluator_config.threshold

    return NumericEvaluationResult(
        score=score,
        details=json.dumps({
            "threshold": self.evaluator_config.threshold,
            "passed": passed,
            "strict": self.evaluator_config.strict,
        })
    )
```

## Troubleshooting

### Evaluator Not Found

**Error**: `Could not find '<filename>' in evals/evaluators/custom folder`

**Solution**: Ensure your evaluator file is in the correct directory:

```bash
# Check file location
ls evals/evaluators/custom/

# File should be: evals/evaluators/custom/my_evaluator.py
```

### Class Not Inheriting from BaseEvaluator

**Error**: `Could not find a class inheriting from BaseEvaluator in <filename>`

**Solution**: Verify your class properly inherits from `BaseEvaluator`:

```python
from uipath.eval.evaluators import BaseEvaluator

class MyEvaluator(BaseEvaluator[...]):  # ✓ Correct
    pass

class MyEvaluator:  # ✗ Wrong - missing inheritance
    pass
```

### Missing get_evaluator_id Method

**Error**: `Error getting evaluator ID`

**Solution**: Implement the required `get_evaluator_id` class method:

```python
@classmethod
def get_evaluator_id(cls) -> str:
    """Get the evaluator ID."""
    return "MyUniqueEvaluatorId"
```

### Type Inconsistency

**Error**: `Type inconsistency in evaluator: Config expects criteria type X`

**Solution**: Ensure your config's generic parameter matches your evaluator's criteria type:

```python
# ✓ Correct - matching types
class MyCriteria(BaseEvaluationCriteria):
    pass

class MyConfig(BaseEvaluatorConfig[MyCriteria]):  # Uses MyCriteria
    pass

class MyEvaluator(BaseEvaluator[MyCriteria, MyConfig, str]):  # Also uses MyCriteria
    pass

# ✗ Wrong - mismatched types
class MyEvaluator(BaseEvaluator[OtherCriteria, MyConfig, str]):  # Mismatch!
    pass
```

## CLI Commands Reference

### Create New Evaluator

```bash
uipath add evaluator <evaluator-name>
```

Creates a new evaluator template in `evals/evaluators/custom/`.

### Register Evaluator

```bash
uipath register evaluator <evaluator-file.py>
```

Validates and generates configuration files for the evaluator.

## Running Your Custom Evaluators

Once registered, your custom evaluators can be used in evaluation sets just like built-in evaluators. See the [Evaluation Overview - Running Evaluations](index.md#running-evaluations) section for details on using the `uipath eval` command.

## Related Documentation

- [Evaluation Overview](index.md): Understanding the evaluation framework and running evaluations
- [Exact Match Evaluator](exact_match.md): Example of a deterministic evaluator
- [Tool Call Args Evaluator](tool_call_args.md): Working with tool call data
- [LLM Judge Output](llm_judge_output.md): LLM-based evaluation patterns

