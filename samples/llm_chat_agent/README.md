# LLM Chat Agent Sample

This sample demonstrates how to create an agent that makes actual LLM calls using the UiPath LLM Gateway services.

## Features

- **Simple Chat Completions**: Make basic LLM calls for question answering
- **Tool/Function Calling**: Enable LLM to use real API integrations
  - **Weather Tool**: Real-time weather data via OpenWeatherMap API
  - **Calculator Tool**: Math calculations via Newton API with local fallback
- **Multi-turn Conversations**: Handle follow-up responses after tool execution
- **Tracing**: Built-in observability with OpenTelemetry tracing
- **Type Safety**: Full Pydantic models for inputs and outputs

## Setup

### 1. Install Dependencies

From the repository root:

```bash
pip install -e .
```

Or install specific dependencies:

```bash
cd samples/llm_chat_agent
pip install -r requirements.txt
```

### 2. Configure Environment

Set the required environment variables:

**UiPath Configuration:**
```bash
export UIPATH_URL="https://cloud.uipath.com/your-org/your-tenant"
export UIPATH_ACCESS_TOKEN="your_access_token_here"
```

**Weather API (OpenWeatherMap):**
```bash
export OPENWEATHER_API_KEY="your_openweather_api_key"
```

Get a free API key at: https://openweathermap.org/api

**Note:** The calculator tool uses the free Newton API and doesn't require an API key. It also has a local fallback using Python's eval.

### 3. Run the Agent

```bash
python agent.py
```

## Usage Examples

### Example 1: Simple Question (No Tools)

```python
from agent import main, AgentInput
import asyncio

input = AgentInput(
    query="What is the capital of France?",
    use_tools=False
)
result = asyncio.run(main(input))
print(result.response)
```

**Output:**
```
The capital of France is Paris.
```

### Example 2: Weather Query (With Tools)

```python
input = AgentInput(
    query="What's the weather like in Tokyo?",
    use_tools=True
)
result = asyncio.run(main(input))
print(result.response)
print(f"Tools used: {result.tool_calls_made}")
```

**Output:**
```
The weather in Tokyo is currently scattered clouds with a temperature of 68.5°F and humidity at 62%.
Tools used: ['get_current_weather']
```

**Note:** This makes a real API call to OpenWeatherMap and returns actual current weather data.

### Example 3: Calculation (With Tools)

```python
input = AgentInput(
    query="What is 25 * 47 + 123?",
    use_tools=True
)
result = asyncio.run(main(input))
print(result.response)
print(f"Tools used: {result.tool_calls_made}")
```

**Output:**
```
The result of 25 * 47 + 123 is 1,298.
Tools used: ['calculate']
```

**Note:** This makes a real API call to Newton API for calculation. If the API is unavailable, it falls back to local evaluation.

## Key Components

### LLM Service Initialization

```python
from uipath._config import Config
from uipath._execution_context import ExecutionContext
from uipath._services.llm_gateway_service import (
    ChatModels,
    UiPathLlmChatService,
)

config = Config()  # Loads from environment
execution_context = ExecutionContext()
llm_service = UiPathLlmChatService(config=config, execution_context=execution_context)
```

### Making Chat Completions

```python
result = await llm_service.chat_completions(
    messages=messages,
    model=ChatModels.gpt_4o_mini_2024_07_18,
    max_tokens=500,
    temperature=0.7,
    tools=[WEATHER_TOOL, CALCULATOR_TOOL],  # Optional
    tool_choice=AutoToolChoice(type="auto"),  # Optional
)
```

### Tool Definition

```python
from uipath.models.llm_gateway import (
    ToolDefinition,
    ToolFunctionDefinition,
    ToolParametersDefinition,
    ToolPropertyDefinition,
)

WEATHER_TOOL = ToolDefinition(
    type="function",
    function=ToolFunctionDefinition(
        name="get_current_weather",
        description="Get the current weather information for a specific city",
        parameters=ToolParametersDefinition(
            type="object",
            properties={
                "city": ToolPropertyDefinition(
                    type="string",
                    description="The name of the city"
                )
            },
            required=["city"],
        ),
    ),
)
```

### Tool Execution

```python
# Check if LLM wants to call tools
if result.choices[0].message.tool_calls:
    for tool_call in result.choices[0].message.tool_calls:
        # Execute the tool
        tool_result = await execute_tool_call(
            tool_call.name,
            tool_call.arguments
        )

        # Add result back to conversation
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": str(tool_result),
        })

    # Make follow-up LLM call with tool results
    result = await llm_service.chat_completions(messages=messages, ...)
```

## Available Models

The agent uses `ChatModels.gpt_4o_mini_2024_07_18` by default. Other available models:

- `ChatModels.gpt_4`
- `ChatModels.gpt_4_turbo_2024_04_09`
- `ChatModels.gpt_4o_2024_05_13`
- `ChatModels.gpt_4o_2024_08_06`
- `ChatModels.gpt_4o_mini_2024_07_18`
- `ChatModels.o3_mini`

## Tracing and Observability

The agent uses the `@traced()` decorator for automatic tracing:

```python
from uipath.tracing import traced

@traced()
async def main(input: AgentInput) -> AgentOutput:
    # Your implementation
    pass
```

This creates OpenTelemetry spans for each function, allowing you to track:
- LLM call latency
- Tool execution times
- Token usage
- Error rates

## Adding Custom Tools

To add a new tool:

1. **Implement the tool function:**

```python
@traced()
async def my_custom_tool(param: str) -> Dict[str, Any]:
    """Tool implementation."""
    return {"result": "value"}
```

2. **Define the tool schema:**

```python
MY_TOOL = ToolDefinition(
    type="function",
    function=ToolFunctionDefinition(
        name="my_custom_tool",
        description="Description of what the tool does",
        parameters=ToolParametersDefinition(
            type="object",
            properties={
                "param": ToolPropertyDefinition(
                    type="string",
                    description="Parameter description"
                )
            },
            required=["param"],
        ),
    ),
)
```

3. **Add to tool execution:**

```python
async def execute_tool_call(tool_name: str, tool_arguments: Dict[str, Any]) -> Dict[str, Any]:
    if tool_name == "my_custom_tool":
        return await my_custom_tool(**tool_arguments)
    # ... other tools
```

4. **Pass to LLM:**

```python
result = await llm_service.chat_completions(
    messages=messages,
    tools=[WEATHER_TOOL, CALCULATOR_TOOL, MY_TOOL],
    # ...
)
```

## Troubleshooting

### Authentication Errors

If you see authentication errors, ensure:
- Your `.env` file has the correct credentials
- Your OAuth client has the necessary permissions
- Your tenant name is correct

### Import Errors

If you encounter import errors:
```bash
# From repository root
pip install -e .
```

### Connection Timeouts

If requests timeout:
- Check your `UIPATH_BASE_URL` is accessible
- Verify network connectivity to UiPath Orchestrator
- Consider increasing timeout values in the Config

## Related Samples

- `weather_tools/` - Shows tool calling with trajectory evaluation
- `google-ADK-agent/` - Example using Google ADK with Gemini models
- `calculator/` - Simple calculator agent example

## References

- [UiPath Python SDK Documentation](https://docs.uipath.com/automation-suite/automation-cloud/latest/user-guide/python-sdk)
- [LLM Gateway Service API](../../src/uipath/_services/llm_gateway_service.py)
- [Tool Calling Models](../../src/uipath/models/llm_gateway.py)
