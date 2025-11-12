# Weather Tools Mocked Agent

A sample mocked agent demonstrating multiple tool calls with trajectory evaluation and tool call evaluators.

## Overview

This is a **mocked agent** designed for testing and demonstration purposes. It does not make real weather API calls. Instead, it returns simulated weather data from hardcoded values to demonstrate:

- How to structure tools with proper tracing for trajectory evaluation
- How multiple tool calls are captured and validated
- How tool call evaluators verify tool usage, arguments, and outputs
- Best practices for integrating mocked tools with UiPath's evaluation framework
- Custom serialization with content wrapper pattern

All weather data is simulated for five cities (New York, London, Tokyo, Paris, Sydney) with predefined responses.

## Tools

The agent provides five mocked tools that return simulated data:

1. **get_temperature** - Returns simulated temperature in fahrenheit
2. **get_weather_condition** - Returns simulated weather condition (sunny, rainy, etc.)
3. **get_humidity** - Returns simulated humidity percentage
4. **get_forecast** - Returns simulated weather forecast text
5. **get_weather_alerts** - Returns simulated weather alerts

**Note:** All tools return hardcoded responses wrapped in a `{"content": {...}}` structure for demonstration purposes. No actual weather APIs are called.

## Data Models

### Input Model
```python
@dataclass
class WeatherInput:
    city: City  # Enum: NEW_YORK, LONDON, TOKYO, PARIS, SYDNEY
    action: Literal["get_weather", "get_forecast", "get_alerts"]
```

### Output Model
```python
class WeatherOutput(_WeatherOutputContent):
    content: _WeatherOutputContent  # Wraps all data under "content" key

class _WeatherOutputContent(BaseModel):
    city: str
    temperature: float
    condition: WeatherCondition  # Enum: SUNNY, CLOUDY, RAINY, SNOWY
    humidity: int
    forecast: str | None = None
    alerts: list[str] | None = None
```

## Multiple Tool Calls

The agent demonstrates multiple tool calls in a single execution:

### Example: "get_weather" action
```
1. get_temperature("New York")       -> {"content": {"temperature": 72.5, "unit": "fahrenheit"}}
2. get_weather_condition("New York") -> {"content": {"condition": "sunny"}}
3. get_humidity("New York")          -> {"content": {"humidity": 60}}
```

### Example: "get_forecast" action
```
1. get_temperature("Paris")       -> {"content": {"temperature": 18.0, "unit": "fahrenheit"}}
2. get_weather_condition("Paris") -> {"content": {"condition": "cloudy"}}
3. get_humidity("Paris")          -> {"content": {"humidity": 70}}
4. get_forecast("Paris")          -> {"content": {"forecast": "Cloudy with a chance of rain..."}}
```

### Example: "get_alerts" action
```
1. get_temperature("London")       -> {"content": {"temperature": 15.0, "unit": "fahrenheit"}}
2. get_weather_condition("London") -> {"content": {"condition": "rainy"}}
3. get_humidity("London")          -> {"content": {"humidity": 80}}
4. get_weather_alerts("London")    -> {"content": {"alerts": ["Heavy rain warning until 6 PM"]}}
```

## Trajectory Evaluation

Each tool call creates its own OTEL span with the `tool.name` attribute set, allowing UiPath's trajectory evaluation to extract:

### Tool Call Sequence
The evaluator extracts tool names in order:
```python
["get_temperature", "get_weather_condition", "get_humidity", "get_forecast"]
```

### Tool Arguments
Each tool's input arguments are captured:
```python
ToolCall(name="get_temperature", args={"city": "New York"})
ToolCall(name="get_weather_condition", args={"city": "New York"})
...
```

### Tool Outputs
Each tool's output is captured with content wrapper:
```python
ToolOutput(name="get_temperature", output='{"content": {"temperature": 72.5, "unit": "fahrenheit"}}')
ToolOutput(name="get_weather_condition", output='{"content": {"condition": "sunny"}}')
...
```

## Implementation Details

### Decorator Stack
Each mocked tool uses a specific decorator order to ensure proper tracing:

```python
@traced(name="get_temperature", span_type="tool")  # Creates OTEL spans for tracing
@mockable(example_calls=...) # Provides mock data during evaluation
async def get_temperature(city: str) -> dict:
    """Returns simulated temperature data"""
    city_enum = City(city)
    temps = {City.NEW_YORK: 72.5, City.LONDON: 15.0, ...}
    return {"content": {"temperature": temps.get(city_enum, 20.0), "unit": "fahrenheit"}}
```

### Tool Invocation
Mocked tools are invoked directly as async functions (not LangChain tools):

```python
temp_data = await get_temperature(city)
```

This ensures:
1. `@traced()` creates an OTEL span for the tool call
2. `@mockable()` can provide mock responses during evaluation
3. The trajectory evaluator can extract the tool call with its arguments and output
4. Simulated data is returned from hardcoded dictionaries with content wrapper

### Content Wrapper Pattern
All tool outputs and final agent output use a consistent `{"content": {...}}` structure:
- Tool outputs: `{"content": {"temperature": 72.5, "unit": "fahrenheit"}}`
- Agent output: `{"content": {"city": "NYC", "temperature": 72.5, ...}}`

This pattern ensures consistent serialization and makes it easy to extract the actual data from the wrapper.

## Running Evaluations

### Basic Evaluation
Run the evaluation to test the mocked agent's behavior:

```bash
uv run uipath eval samples/weather_tools/main.py samples/weather_tools/evaluations/eval-sets/default.json --workers 1
```

### Evaluation Output
The evaluators will verify the mocked agent's behavior:
- ✅ **Trajectory evaluation**: Validates tool call sequence and orchestration logic
- ✅ **Tool call count**: Verifies correct number of each tool call
- ✅ **Tool call order**: Ensures tools are called in the expected sequence
- ✅ **Tool call args**: Validates arguments passed to each tool
- ✅ **Tool call output**: Checks that tool outputs match expectations with content wrapper
- ✅ **JSON similarity**: Compares final agent output structure
- ✅ **Exact match**: Validates specific output values

## Test Cases

The eval set includes 5 test cases covering:
1. Basic weather check (3 tool calls)
2. Weather with forecast (4 tool calls)
3. Weather with alerts (4 tool calls)
4. Sunny weather conditions (3 tool calls)
5. Tokyo forecast sequence validation (4 tool calls)

Each test case validates that the agent calls the correct tools in the right order with proper arguments and content-wrapped outputs.

## Usage Examples

### Running the Agent
```python
from main import main, WeatherInput, City

# Basic weather check
input_data = WeatherInput(city=City.NEW_YORK, action="get_weather")
result = await main(input_data)
print(result.model_dump())  # {"content": {"city": "New York", "temperature": 72.5, ...}}

# Weather with forecast
input_data = WeatherInput(city=City.PARIS, action="get_forecast")
result = await main(input_data)
print(result.model_dump())  # Includes forecast in content
```

### Custom Serialization
The `WeatherOutput` class includes custom serialization methods:
```python
# Get content-wrapped dictionary
data = result.model_dump()

# Get JSON string with content wrapper
json_str = result.to_json()

# Exclude None values
data_clean = result.model_dump(exclude_none=True)
```
