# Agent Evaluations

The UiPath SDK provides a comprehensive evaluation framework for assessing agent performance and behavior. This framework enables you to systematically measure and validate agent outputs, execution trajectories, and tool usage patterns.

## Overview

The evaluation framework consists of two main categories of evaluators, organized by what they evaluate:

### Output-Based Evaluators

These evaluators assess the final output/result produced by an agent:

-   **[Contains Evaluator](contains.md)**: Checks if the output contains specific text
-   **[Exact Match Evaluator](exact_match.md)**: Verifies exact string matching
-   **[JSON Similarity Evaluator](json_similarity.md)**: Measures structural similarity between JSON outputs
-   **[LLM Judge Output Evaluator](llm_judge_output.md)**: Uses LLM for semantic output evaluation and quality assessment

### Trajectory-Based Evaluators

These evaluators assess the execution path, decision-making process, and tool usage patterns during agent execution:

-   **[Tool Call Order Evaluator](tool_call_order.md)**: Validates the sequence in which tools are called
-   **[Tool Call Count Evaluator](tool_call_count.md)**: Verifies the frequency of tool calls
-   **[Tool Call Args Evaluator](tool_call_args.md)**: Checks tool call arguments for correctness
-   **[Tool Call Output Evaluator](tool_call_output.md)**: Validates the outputs returned by tool calls
-   **[LLM Judge Trajectory Evaluator](llm_judge_trajectory.md)**: Evaluates agent execution trajectories and decision-making with LLM judgment

## Core Concepts

### Evaluation Criteria

Each evaluator uses specific criteria to define what should be evaluated. Criteria can be specified per test case or set as defaults in the evaluator configuration.

### Evaluation Results

Evaluators return a score (typically between 0 and 1) along with optional details or justification for the score.

### Configuration

Each evaluator has a configuration class that defines:

-   **name**: The evaluator's identifier
-   **default_evaluation_criteria**: Default criteria if not specified per test
-   Evaluator-specific settings (e.g., `case_sensitive`, `strict`, `temperature`)

## Getting Started

To use an evaluator, you typically:

1. Import the evaluator class
2. Create an evaluator instance with configuration
3. Call the `evaluate()` method with agent execution data and criteria

```python
from uipath.eval.evaluators import ExactMatchEvaluator
from uipath.eval.models import AgentExecution

# Sample agent execution (this should be replaced with your agent run data)
agent_execution = AgentExecution(
    agent_input={"query": "Greet the world"},
    agent_output={"result": "hello, world!"},
    agent_trace=[],
)

# Create evaluator
evaluator = ExactMatchEvaluator(
    id="exact-match-1",
    config={
        "name": "ExactMatchEvaluator",
        "case_sensitive": False,
        "target_output_key": "result",
    }
)

# Evaluate
result = await evaluator.validate_and_evaluate_criteria(
    agent_execution=agent_execution,
    evaluation_criteria={"expected_output": {"result": "Hello, World!"}}
)

print(f"Score: {result.score}")
```

## Best Practices

1. **Choose the right category**:
   - Use **Output-Based Evaluators** to validate what the agent produces (final results)
   - Use **Trajectory-Based Evaluators** to validate how the agent achieves results (decision-making and tool usage)

2. **Select appropriate evaluators within categories**:
   - For outputs: Use deterministic evaluators (exact match, contains, JSON similarity) for predictable outputs and LLM judges for semantic/quality assessment
   - For trajectories: Use tool call evaluators for specific validations and LLM judges for holistic behavior assessment

3. **Combine multiple evaluators**: Use different evaluators together for comprehensive evaluation (e.g., exact match for output + tool call order for trajectory)

4. **Set appropriate thresholds**: Define minimum acceptable scores based on your use case

5. **Evaluate both outputs and trajectories**: For complex agents, validate both what they produce and how they produce it

## Reference Documentation

See the individual evaluator pages for detailed information on configuration, usage, and examples.

