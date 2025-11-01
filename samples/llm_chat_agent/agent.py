"""
Sample agent demonstrating actual LLM calls using UiPath LLM Gateway.

This agent shows how to:
1. Make chat completions with LLM models
2. Use tools/function calling with real API integrations
3. Handle multi-turn conversations
4. Use tracing for observability

API Integrations:
- Weather: Uses Open-Meteo API (free, no API key required)
- Calculator: Uses Newton API (free, no API key required) with local eval fallback
"""

import asyncio
import json
import os
from typing import Any, Dict, List

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from uipath._config import Config
from uipath._execution_context import ExecutionContext
from uipath._services.llm_gateway_service import (
    ChatModels,
    UiPathLlmChatService,
)
from uipath.models.llm_gateway import (
    AutoToolChoice,
    ToolDefinition,
    ToolFunctionDefinition,
    ToolParametersDefinition,
    ToolPropertyDefinition,
)
from uipath.tracing import traced

# Load environment variables from .env file if it exists
# This will not override existing environment variables
load_dotenv()


# Input/Output models
class AgentInput(BaseModel):
    """Input model for the agent."""

    query: str = Field(description="User's question or request")
    use_tools: bool = Field(
        default=False, description="Whether to enable tool calling"
    )


class AgentOutput(BaseModel):
    """Output model for the agent."""

    response: str = Field(description="Agent's response to the user")
    tool_calls_made: List[str] = Field(
        default_factory=list, description="Names of tools that were called"
    )


# Tool implementations
@traced()
async def get_current_weather(city: str) -> Dict[str, Any]:
    """
    Get the current weather for a city using Open-Meteo API.

    This makes a real API call to fetch current weather data.
    Open-Meteo is completely free, requires no API key, and has no rate limits for reasonable use.
    Learn more at: https://open-meteo.com/
    """
    try:
        async with httpx.AsyncClient() as client:
            # First, geocode the city name to get coordinates
            # Using Open-Meteo's geocoding API
            geocoding_url = "https://geocoding-api.open-meteo.com/v1/search"
            geocoding_params = {
                "name": city,
                "count": 1,
                "language": "en",
                "format": "json"
            }

            geo_response = await client.get(geocoding_url, params=geocoding_params, timeout=10.0)
            geo_response.raise_for_status()
            geo_data = geo_response.json()

            if not geo_data.get("results"):
                return {
                    "city": city,
                    "error": f"City '{city}' not found",
                }

            # Get the first result
            location = geo_data["results"][0]
            latitude = location["latitude"]
            longitude = location["longitude"]
            city_name = location["name"]
            country = location.get("country", "")

            # Now get the weather data using the coordinates
            weather_url = "https://api.open-meteo.com/v1/forecast"
            weather_params = {
                "latitude": latitude,
                "longitude": longitude,
                "current": "temperature_2m,relative_humidity_2m,weather_code",
                "temperature_unit": "fahrenheit",
                "timezone": "auto"
            }

            weather_response = await client.get(weather_url, params=weather_params, timeout=10.0)
            weather_response.raise_for_status()
            weather_data = weather_response.json()

            current = weather_data["current"]

            # Map weather codes to descriptions
            # https://open-meteo.com/en/docs
            weather_code = current.get("weather_code", 0)
            condition = get_weather_description(weather_code)

            return {
                "city": f"{city_name}, {country}" if country else city_name,
                "temperature": current["temperature_2m"],
                "condition": condition,
                "humidity": current["relative_humidity_2m"],
                "unit": "fahrenheit",
            }

    except httpx.HTTPStatusError as e:
        return {
            "city": city,
            "error": f"API error: {e.response.status_code}",
        }
    except Exception as e:
        return {
            "city": city,
            "error": f"Failed to fetch weather data: {str(e)}",
        }


def get_weather_description(code: int) -> str:
    """
    Convert Open-Meteo weather codes to human-readable descriptions.
    Based on WMO Weather interpretation codes.
    """
    weather_codes = {
        0: "clear sky",
        1: "mainly clear",
        2: "partly cloudy",
        3: "overcast",
        45: "foggy",
        48: "depositing rime fog",
        51: "light drizzle",
        53: "moderate drizzle",
        55: "dense drizzle",
        61: "slight rain",
        63: "moderate rain",
        65: "heavy rain",
        71: "slight snow fall",
        73: "moderate snow fall",
        75: "heavy snow fall",
        77: "snow grains",
        80: "slight rain showers",
        81: "moderate rain showers",
        82: "violent rain showers",
        85: "slight snow showers",
        86: "heavy snow showers",
        95: "thunderstorm",
        96: "thunderstorm with slight hail",
        99: "thunderstorm with heavy hail",
    }
    return weather_codes.get(code, "unknown")


@traced()
async def calculate(expression: str) -> Dict[str, Any]:
    """
    Perform a mathematical calculation using Newton API.

    This makes a real API call to evaluate mathematical expressions.
    The Newton API is free and doesn't require an API key.

    Args:
        expression: A mathematical expression to evaluate (e.g., "2 + 2", "10 * 5")

    Returns:
        Dictionary with the result or error message
    """
    try:
        # For simple arithmetic, we'll use Newton API's simplify endpoint
        # Newton API: https://newton.vercel.app/
        async with httpx.AsyncClient() as client:
            # URL encode the expression
            encoded_expr = expression.replace(" ", "")
            url = f"https://newton.vercel.app/api/v2/simplify/{encoded_expr}"

            response = await client.get(url, timeout=10.0)
            response.raise_for_status()

            data = response.json()

            if data.get("result"):
                return {
                    "expression": expression,
                    "result": data["result"]
                }
            else:
                return {
                    "expression": expression,
                    "error": "Could not evaluate expression"
                }

    except httpx.HTTPStatusError as e:
        return {
            "expression": expression,
            "error": f"API error: {e.response.status_code}"
        }
    except Exception as e:
        # Fallback to local evaluation for simple cases
        try:
            allowed_chars = set("0123456789+-*/()%. ")
            if not all(c in allowed_chars for c in expression):
                return {"expression": expression, "error": "Invalid characters in expression"}

            result = eval(expression)
            return {
                "expression": expression,
                "result": result,
                "note": "Evaluated locally (API unavailable)"
            }
        except Exception as eval_error:
            return {
                "expression": expression,
                "error": f"Failed to calculate: {str(e)}, fallback error: {str(eval_error)}"
            }


# Tool definitions for LLM
WEATHER_TOOL = ToolDefinition(
    type="function",
    function=ToolFunctionDefinition(
        name="get_current_weather",
        description="Get the current weather information for a specific city",
        parameters=ToolParametersDefinition(
            type="object",
            properties={
                "city": ToolPropertyDefinition(
                    type="string", description="The name of the city"
                )
            },
            required=["city"],
        ),
    ),
)

CALCULATOR_TOOL = ToolDefinition(
    type="function",
    function=ToolFunctionDefinition(
        name="calculate",
        description="Perform mathematical calculations. Can evaluate expressions like '2 + 2' or '10 * 5'",
        parameters=ToolParametersDefinition(
            type="object",
            properties={
                "expression": ToolPropertyDefinition(
                    type="string",
                    description="The mathematical expression to evaluate",
                )
            },
            required=["expression"],
        ),
    ),
)


@traced()
async def execute_tool_call(tool_name: str, tool_arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a tool based on its name and arguments.

    Args:
        tool_name: Name of the tool to execute
        tool_arguments: Arguments to pass to the tool

    Returns:
        Result from the tool execution
    """
    if tool_name == "get_current_weather":
        return await get_current_weather(**tool_arguments)
    elif tool_name == "calculate":
        return await calculate(**tool_arguments)
    else:
        return {"error": f"Unknown tool: {tool_name}"}


@traced()
async def main(input: AgentInput) -> AgentOutput:
    """
    Main agent function that makes LLM calls.

    This demonstrates:
    1. Simple chat completions
    2. Tool/function calling
    3. Multi-turn conversations with tool results
    """
    # Initialize the LLM service
    # Get credentials from environment variables
    base_url = os.environ.get("UIPATH_URL")
    access_token = os.environ.get("UIPATH_ACCESS_TOKEN")

    if not base_url or not access_token:
        error_msg = """
        Missing required environment variables. Please set:
        - UIPATH_URL: Your UiPath Orchestrator URL (e.g., https://cloud.uipath.com/org/tenant)
        - UIPATH_ACCESS_TOKEN: Your API access token

        You can set them in your shell:
        export UIPATH_URL="https://cloud.uipath.com/your-org/your-tenant"
        export UIPATH_ACCESS_TOKEN="your_token_here"

        Or create a .env file with these variables.
        """
        print(error_msg)
        return AgentOutput(response=error_msg.strip(), tool_calls_made=[])

    config = Config(base_url=base_url, secret=access_token)
    execution_context = ExecutionContext()
    llm_service = UiPathLlmChatService(config=config, execution_context=execution_context)

    # Prepare the conversation
    messages = [
        {
            "role": "system",
            "content": "You are a helpful assistant that can answer questions and use tools when needed.",
        },
        {"role": "user", "content": input.query},
    ]

    tool_calls_made = []

    try:
        if input.use_tools:
            # Make LLM call with tool support
            print(f"Making LLM call with tools enabled for query: {input.query}")

            result = await llm_service.chat_completions(
                messages=messages,
                model=ChatModels.gpt_4o_mini_2024_07_18,
                max_tokens=500,
                temperature=0.7,
                tools=[WEATHER_TOOL, CALCULATOR_TOOL],
                tool_choice=AutoToolChoice(type="auto"),
            )

            # Check if the model wants to call tools
            if result.choices[0].message.tool_calls:
                print(f"LLM requested {len(result.choices[0].message.tool_calls)} tool call(s)")

                # Add assistant's response to messages
                # Convert tool calls to proper format
                tool_calls_for_message = []
                for tc in result.choices[0].message.tool_calls:
                    tool_call_dict = {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": tc.arguments if isinstance(tc.arguments, str) else json.dumps(tc.arguments),
                        },
                    }
                    tool_calls_for_message.append(tool_call_dict)

                # Execute each tool call and collect results
                tool_results_text = []
                for tool_call in result.choices[0].message.tool_calls:
                    print(f"Executing tool: {tool_call.name} with args: {tool_call.arguments}")
                    tool_calls_made.append(tool_call.name)

                    # Execute the tool
                    tool_result = await execute_tool_call(
                        tool_call.name, tool_call.arguments
                    )
                    tool_results_text.append(f"{tool_call.name}: {json.dumps(tool_result)}")

                # Add a simple assistant acknowledgment and user message with tool results
                # NOTE: UiPath LLM Gateway API doesn't support assistant messages with tool_calls
                # or messages with "tool" role, so we work around it
                messages.append(
                    {
                        "role": "assistant",
                        "content": "Let me check that for you.",
                    }
                )
                messages.append(
                    {
                        "role": "user",
                        "content": f"Here are the tool results: {'; '.join(tool_results_text)}. Please provide a natural language response to my original question.",
                    }
                )

                # Make another LLM call with tool results
                # No need to pass tools again since we've already executed them
                print("Making follow-up LLM call with tool results")
                result = await llm_service.chat_completions(
                    messages=messages,
                    model=ChatModels.gpt_4o_mini_2024_07_18,
                    max_tokens=500,
                    temperature=0.7,
                )

            response = result.choices[0].message.content or "No response generated"
            print(f"Final response: {response}")

        else:
            # Simple chat completion without tools
            print(f"Making simple LLM call for query: {input.query}")

            result = await llm_service.chat_completions(
                messages=messages,
                model=ChatModels.gpt_4o_mini_2024_07_18,
                max_tokens=300,
                temperature=0.7,
            )

            response = result.choices[0].message.content or "No response generated"
            print(f"Response: {response}")

        return AgentOutput(response=response, tool_calls_made=tool_calls_made)

    except Exception as e:
        error_msg = f"Error making LLM call: {str(e)}"
        print(error_msg)
        return AgentOutput(response=error_msg, tool_calls_made=tool_calls_made)


# Example usage
if __name__ == "__main__":
    # Example 1: Simple question without tools
    print("=" * 80)
    print("Example 1: Simple question")
    print("=" * 80)
    input1 = AgentInput(
        query="What is the capital of France?",
        use_tools=False
    )
    result1 = asyncio.run(main(input1))
    print(f"\nQuery: {input1.query}")
    print(f"Response: {result1.response}")
    print(f"Tools used: {result1.tool_calls_made or 'None'}")

    # Example 2: Question that requires weather tool
    print("\n" + "=" * 80)
    print("Example 2: Weather query with tools")
    print("=" * 80)
    input2 = AgentInput(
        query="What's the weather like in Tokyo?",
        use_tools=True
    )
    result2 = asyncio.run(main(input2))
    print(f"\nQuery: {input2.query}")
    print(f"Response: {result2.response}")
    print(f"Tools used: {result2.tool_calls_made}")

    # Example 3: Question that requires calculator tool
    print("\n" + "=" * 80)
    print("Example 3: Calculation with tools")
    print("=" * 80)
    input3 = AgentInput(
        query="What is 25 * 47 + 123?",
        use_tools=True
    )
    result3 = asyncio.run(main(input3))
    print(f"\nQuery: {input3.query}")
    print(f"Response: {result3.response}")
    print(f"Tools used: {result3.tool_calls_made}")
