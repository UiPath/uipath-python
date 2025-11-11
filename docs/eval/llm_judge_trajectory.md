# LLM Judge Trajectory Evaluators

LLM Judge Trajectory Evaluators use Language Models to assess the quality of agent execution trajectories - the sequence of decisions and actions an agent takes. These evaluators are good options for validating that agents follow expected execution behaviors when standard trajectory evaluators do not weigh specific mistakes too well or are too hard to configure. However, the recommended practice for most use cases involves acquiring comprehensive trajectory annotations and adopting deterministic trajectory evaluators.

## Overview

We provide two variants of LLM Judge Trajectory Evaluators:

1. **LLM Judge Trajectory Evaluator** (`llm-judge-trajectory-similarity`): General trajectory evaluation
2. **LLM Judge Trajectory Simulation Evaluator** (`llm-judge-trajectory-simulation`): Specialized for tool simulation scenarios

**Use Cases**:

-   Validate agent decision-making processes
-   Ensure agents follow expected execution paths
-   Evaluate tool usage patterns and sequencing
-   Assess agent behavior in complex scenarios
-   Validate tool simulation accuracy (where tool responses are mocked)

**Returns**: Continuous score from 0.0 to 1.0 with justification

## LLM Service Integration

LLM Judge evaluators require an LLM service to perform evaluations. By default, the evaluators use the **UiPathLlmService** to handle LLM requests, which automatically integrates with your configured LLM providers through the UiPath platform.

### Custom LLM Service

You can supply a custom LLM service that supports the following request format:

```python
{
    "model": "model-name",
    "messages": [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "evaluation prompt"}
    ],
    "response_format": {
        "type": "json_schema",
        "json_schema": {
            "name": "evaluation_response",
            "schema": {
                # JSON schema for structured output
            }
        }
    },
    "max_tokens": 1000,  # or None
    "temperature": 0.0
}
```

The LLM service must:

- Accept messages with `system` and `user` roles
- Support structured output via `response_format` with JSON schema
- Return responses conforming to the specified schema
- Handle `temperature` and `max_tokens` parameters

### Model Selection

When configuring the evaluator, specify the model name according to your LLM service's conventions:

```python
evaluator = LLMJudgeTrajectoryEvaluator(
    id="trajectory-judge-1",
    config={
        "name": "LLMJudgeTrajectoryEvaluator",
        "model": "gpt-4o-2024-11-20",  # Use your service's model naming
        "temperature": 0.0
    }
)
```

!!! note "UiPathLlmService"
    The default `UiPathLlmService` supports multiple LLM providers configured through the UiPath platform. Model names follow the provider's conventions (e.g., `gpt-4o-2024-11-20` for OpenAI, `claude-3-5-sonnet-20241022` for Anthropic).

## LLM Judge Trajectory Evaluator

### Configuration

#### LLMJudgeTrajectoryEvaluatorConfig

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | `"LLMJudgeTrajectoryEvaluator"` | The evaluator's name |
| `prompt` | `str` | Default trajectory prompt | Custom evaluation prompt |
| `model` | `str` | `""` | LLM model to use for judgment |
| `temperature` | `float` | `0.0` | LLM temperature (0.0 for deterministic) |
| `max_tokens` | `int or None` | `None` | Maximum tokens for LLM response |
| `default_evaluation_criteria` | `TrajectoryEvaluationCriteria or None` | `None` | Default criteria |

### Evaluation Criteria

#### TrajectoryEvaluationCriteria

| Parameter | Type | Description |
|-----------|------|-------------|
| `expected_agent_behavior` | `str` | Description of the expected agent behavior |

### Prompt Placeholders

The prompt template supports these placeholders:

- `{{AgentRunHistory}}`: The agent's execution trace/trajectory
- `{{ExpectedAgentBehavior}}`: The expected behavior description
- `{{UserOrSyntheticInput}}`: The input provided to the agent
- `{{SimulationInstructions}}`: Tool simulation instructions specifying how tools should respond (for simulation variant only)

### Examples

#### Basic Trajectory Evaluation

```python
from uipath.eval.evaluators import LLMJudgeTrajectoryEvaluator
from uipath.eval.models import AgentExecution

agent_execution = AgentExecution(
    agent_input={"user_query": "Book a flight to Paris"},
    agent_output={"booking_id": "FL123", "status": "confirmed"},
    agent_trace=[
        # Trace contains spans showing the agent's execution path
        # Each span represents a step in the agent's decision-making
    ]
)

evaluator = LLMJudgeTrajectoryEvaluator(
    id="trajectory-judge-1",
    config={
        "name": "LLMJudgeTrajectoryEvaluator",
        # Use the UiPathLlmChatService convention for model names; this should be changed according to selected service
        "model": "gpt-4o-2024-11-20",
        "temperature": 0.0
    }
)

result = await evaluator.validate_and_evaluate_criteria(
    agent_execution=agent_execution,
    evaluation_criteria={
        "expected_agent_behavior": """
        The agent should:
        1. Search for available flights to Paris
        2. Present options to the user
        3. Process the booking
        4. Confirm the reservation
        """
    }
)

print(f"Score: {result.score}")
print(f"Justification: {result.details}")
```

#### Validating Tool Usage Sequence

```python
agent_execution = AgentExecution(
    agent_input={"task": "Update user profile and send notification"},
    agent_output={"status": "completed"},
    agent_trace=[
        # Spans showing: validate_user -> update_profile -> send_notification
    ]
)

evaluator = LLMJudgeTrajectoryEvaluator(
    id="trajectory-tools",
    config={
        "name": "LLMJudgeTrajectoryEvaluator",
        "model": "gpt-4o-2024-11-20",
        "temperature": 0.0
    }
)

result = await evaluator.validate_and_evaluate_criteria(
    agent_execution=agent_execution,
    evaluation_criteria={
        "expected_agent_behavior": """
        The agent must:
        1. First validate the user exists
        2. Update the profile in the database
        3. Send a confirmation notification
        This sequence must be followed to ensure data integrity.
        """
    }
)

print(f"Score: {result.score}")
print(f"Justification: {result.details}")
```

#### Custom Evaluation Prompt

```python
custom_prompt = """
Analyze the agent's execution path and compare it with the expected behavior.

Agent Run History:
{{AgentRunHistory}}

Expected Agent Behavior:
{{ExpectedAgentBehavior}}

User Input:
{{UserOrSyntheticInput}}

Evaluate:
1. Did the agent follow the expected sequence?
2. Were all necessary steps completed?
3. Was the decision-making logical and efficient?

Provide a score from 0-100.
"""

evaluator = LLMJudgeTrajectoryEvaluator(
    id="trajectory-custom",
    config={
        "name": "LLMJudgeTrajectoryEvaluator",
        "model": "gpt-4o-2024-11-20",
        "prompt": custom_prompt,
        "temperature": 0.0
    }
)

# ... use evaluator
```

## LLM Judge Trajectory Simulation Evaluator

This variant is specialized for evaluating agent behavior in **tool simulation scenarios**, where tool responses are mocked/simulated during agent execution.

### What is Tool Simulation?

In tool simulation:

1. **Simulation Engine**: Mocks tool responses based on simulation instructions
2. **Agent Unawareness**: The agent doesn't know tool responses are simulated
3. **Controlled Testing**: Allows testing agent behavior with predictable tool responses
4. **Evaluation Focus**: Assesses whether the agent behaves correctly given the simulated tool responses

The evaluator checks if:
- The simulation was successful (tools responded as instructed)
- The agent behaved according to expectations given the simulated responses
- The agent's decision-making aligns with expected behavior in the simulated scenario

### Configuration

#### LLMJudgeTrajectorySimulationEvaluatorConfig

Same as `LLMJudgeTrajectoryEvaluatorConfig` but with:

- **name**: `"LLMJudgeTrajectorySimulationEvaluator"`
- **prompt**: Specialized prompt for tool simulation evaluation that considers:
  - Simulation instructions (how tools should respond)
  - Whether the simulated tool responses matched instructions
  - Agent behavior given the simulated responses

### Examples

#### Tool Simulation Trajectory Evaluation

```python
from uipath.eval.evaluators import LLMJudgeTrajectorySimulationEvaluator

agent_execution = AgentExecution(
    agent_input={"query": "Book a flight to Paris for tomorrow"},
    agent_output={"booking_id": "FL123", "status": "confirmed"},
    agent_trace=[
        # Execution spans showing tool calls and their simulated responses
    ],
    simulation_instructions="""
    Simulate the following tool responses:
    - search_flights tool: Return 3 available flights with prices
    - book_flight tool: Return booking confirmation with ID "FL123"
    - send_confirmation_email tool: Return success status
    Mock the tools to respond as if it's a Tuesday in March with normal availability.
    """
)

evaluator = LLMJudgeTrajectorySimulationEvaluator(
    id="sim-trajectory-1",
    config={
        "name": "LLMJudgeTrajectorySimulationEvaluator",
        "model": "gpt-4o-2024-11-20",
        "temperature": 0.0
    }
)

result = await evaluator.validate_and_evaluate_criteria(
    agent_execution=agent_execution,
    evaluation_criteria={
        "expected_agent_behavior": """
        The agent should:
        1. Call search_flights to find available options
        2. Present flight options to the user (simulated in conversation)
        3. Call book_flight with appropriate parameters
        4. Confirm the booking with the user
        5. Call send_confirmation_email to notify the user
        """
    }
)

print(f"Score: {result.score}")
print(f"Justification: {result.details}")
```

## Understanding Agent Traces

The `agent_trace` contains execution spans that show:

- Tool calls made by the agent
- LLM reasoning steps
- Decision points
- Action sequences
- Intermediate results

Example trace structure:
```python
agent_trace = [
    {
        "name": "search_flights",
        "type": "tool",
        "inputs": {"destination": "Paris"},
        "output": {"flights": [...]}
    },
    {
        "name": "llm_reasoning",
        "type": "llm",
        "content": "User wants cheapest option..."
    },
    {
        "name": "book_flight",
        "type": "tool",
        "inputs": {"flight_id": "FL123"},
        "output": {"status": "confirmed"}
    }
]
```

## Best Practices

1. **Write clear behavior descriptions** - Be specific about expected sequences and decision logic
2. **Use temperature 0.0** for consistent evaluations
3. **Include context** - Provide enough detail in expected behavior
4. **Consider partial credit** - LLM can give partial scores for mostly correct trajectories
5. **Review justifications** - Understand why trajectories scored high or low
6. **Combine with tool evaluators** - Use [Tool Call Evaluators](tool_call_order.md) for strict ordering requirements

## When to Use vs Other Evaluators

**Use LLM Judge Trajectory when**:
- Decision-making process matters more than just output
- Agent behavior patterns need validation
- Tool usage sequence is complex but somewhat flexible
- Human-like judgment of execution quality is needed

**Use Tool Call Evaluators when**:
- Strict tool call sequences must be enforced
- Deterministic validation is sufficient
- Exact argument values must match
- Performance and cost are priorities

## Configuration Tips

### Temperature Settings

- **0.0**: Deterministic, consistent results (recommended)
- **0.1**: Slight variation for nuanced judgment
- **>0.3**: Not recommended (too inconsistent)

## Evaluation Criteria Guidelines

When writing `expected_agent_behavior`, include:

1. **Sequential steps**: Numbered or ordered list of expected actions
2. **Decision points**: When the agent should make choices
3. **Conditional logic**: "If X, then Y" scenarios
4. **Success criteria**: What constitutes good behavior
5. **Error handling**: How agent should handle failures

### Good Example

```python
evaluation_criteria = {
    "expected_agent_behavior": """
    The agent should follow this sequence:

    1. Validate user authentication status
       - If not authenticated, request login
       - If authenticated, proceed to step 2

    2. Fetch user's order history
       - Use the get_orders tool with user_id

    3. Identify the problematic order
       - Search for orders with "delayed" status

    4. Provide explanation to user
       - Include order details and delay reason

    5. Offer resolution
       - Present refund or expedited shipping options

    The agent should maintain a helpful tone throughout
    and adapt responses based on user reactions.
    """
}
```

### Poor Example (Too Vague)

```python
evaluation_criteria = {
    "expected_agent_behavior": "Help the user with their order problem"
}
```

## Error Handling

The evaluator will raise `UiPathEvaluationError` if:

- LLM service is unavailable
- Prompt doesn't contain required placeholders
- Agent trace cannot be converted to readable format
- LLM response cannot be parsed

## Performance Considerations

- **Token usage**: Trajectories can be long, increasing token costs
- **Evaluation time**: LLM calls take longer than deterministic evaluators
- **Caching**: Consider caching evaluations for repeated test runs
- **Batch processing**: Evaluate multiple trajectories in parallel when possible

## Related Evaluators

- [LLM Judge Output Evaluator](llm_judge_output.md): For evaluating outputs instead of processes
- [Tool Call Order Evaluator](tool_call_order.md): For strict deterministic sequence validation
- [Tool Call Count Evaluator](tool_call_count.md): For validating tool usage frequencies
- [Tool Call Args Evaluator](tool_call_args.md): For validating tool arguments


