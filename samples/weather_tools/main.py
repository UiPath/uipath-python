import asyncio
import logging
from enum import Enum
from functools import wraps
from typing import Callable, Literal, TypeVar

from opentelemetry import trace
from pydantic import BaseModel
from pydantic.dataclasses import dataclass

from uipath.eval.mocks import ExampleCall, mockable
from uipath.tracing import traced

logger = logging.getLogger(__name__)

T = TypeVar("T")


class City(str, Enum):
    NEW_YORK = "New York"
    LONDON = "London"
    TOKYO = "Tokyo"
    PARIS = "Paris"
    SYDNEY = "Sydney"


class WeatherCondition(str, Enum):
    SUNNY = "sunny"
    CLOUDY = "cloudy"
    RAINY = "rainy"
    SNOWY = "snowy"


@dataclass
class WeatherInput:
    city: City
    action: Literal["get_weather", "get_forecast", "get_alerts"]


class _WeatherOutputContent(BaseModel):
    city: str = ""
    temperature: float = 0.0
    condition: WeatherCondition = WeatherCondition.CLOUDY
    humidity: int = 0
    forecast: str | None = None
    alerts: list[str] | None = None

class WeatherOutput(_WeatherOutputContent):
    content: _WeatherOutputContent

# Mock example for get_temperature tool
GET_TEMPERATURE_EXAMPLES = [
    ExampleCall(
        id="example1",
        input='{"city": "New York"}',
        output='{"temperature": 72.5, "unit": "fahrenheit"}'
    )
]

@traced(name="get_temperature", span_type="tool")
@mockable(example_calls=GET_TEMPERATURE_EXAMPLES)
async def get_temperature(city: str) -> dict:
    """Get the current temperature for a city.

    Args:
        city: The name of the city (e.g., "New York", "London", "Tokyo")

    Returns:
        Dictionary with temperature in fahrenheit and unit
    """
    # Convert string to City enum
    city_enum = City(city)

    # Simulated temperature data
    temps = {
        City.NEW_YORK: 72.5,
        City.LONDON: 15.0,
        City.TOKYO: 25.0,
        City.PARIS: 18.0,
        City.SYDNEY: 22.0,
    }
    return {"content":{"temperature": temps.get(city_enum, 20.0), "unit": "fahrenheit"}}


GET_CONDITION_EXAMPLES = [
    ExampleCall(
        id="example1",
        input='{"city": "London"}',
        output='{"condition": "rainy"}'
    )
]

@traced(name="get_weather_condition", span_type="tool")
@mockable(example_calls=GET_CONDITION_EXAMPLES)
async def get_weather_condition(city: str) -> dict:
    """Get the current weather condition for a city.

    Args:
        city: The name of the city (e.g., "New York", "London", "Tokyo")

    Returns:
        Dictionary with the current weather condition
    """
    # Convert string to City enum
    city_enum = City(city)

    # Simulated weather conditions
    conditions = {
        City.NEW_YORK: WeatherCondition.SUNNY,
        City.LONDON: WeatherCondition.RAINY,
        City.TOKYO: WeatherCondition.CLOUDY,
        City.PARIS: WeatherCondition.CLOUDY,
        City.SYDNEY: WeatherCondition.SUNNY,
    }
    return {"content":{"condition": conditions.get(city_enum, WeatherCondition.CLOUDY).value}}


GET_HUMIDITY_EXAMPLES = [
    ExampleCall(
        id="example1",
        input='{"city": "Tokyo"}',
        output='{"humidity": 65}'
    )
]

@traced(name="get_humidity", span_type="tool")
@mockable(example_calls=GET_HUMIDITY_EXAMPLES)
async def get_humidity(city: str) -> dict:
    """Get the current humidity level for a city.

    Args:
        city: The name of the city (e.g., "New York", "London", "Tokyo")

    Returns:
        Dictionary with the humidity percentage
    """
    # Convert string to City enum
    city_enum = City(city)

    # Simulated humidity data
    humidity_levels = {
        City.NEW_YORK: 60,
        City.LONDON: 80,
        City.TOKYO: 65,
        City.PARIS: 70,
        City.SYDNEY: 55,
    }
    return {"content":{"humidity": humidity_levels.get(city_enum, 60)}}


GET_FORECAST_EXAMPLES = [
    ExampleCall(
        id="example1",
        input='{"city": "Paris"}',
        output='{"forecast": "Cloudy with a chance of rain in the afternoon"}'
    )
]


@traced(name="get_forecast", span_type="tool")
@mockable(example_calls=GET_FORECAST_EXAMPLES)
async def get_forecast(city: str) -> dict:
    """Get the weather forecast for a city.

    Args:
        city: The name of the city (e.g., "New York", "London", "Tokyo")

    Returns:
        Dictionary with the weather forecast
    """
    # Convert string to City enum
    city_enum = City(city)

    # Simulated forecasts
    forecasts = {
        City.NEW_YORK: "Clear skies throughout the day",
        City.LONDON: "Rainy with occasional breaks",
        City.TOKYO: "Overcast with mild temperatures",
        City.PARIS: "Cloudy with a chance of rain in the afternoon",
        City.SYDNEY: "Sunny and warm",
    }
    return {"content":{"forecast": forecasts.get(city_enum, "No forecast available")}}


GET_ALERTS_EXAMPLES = [
    ExampleCall(
        id="example1",
        input='{"city": "London"}',
        output='{"alerts": ["Heavy rain warning until 6 PM"]}'
    )
]

@traced(name="get_weather_alerts", span_type="tool")
@mockable(example_calls=GET_ALERTS_EXAMPLES)
async def get_weather_alerts(city: str) -> dict:
    """Get weather alerts for a city.

    Args:
        city: The name of the city (e.g., "New York", "London", "Tokyo")

    Returns:
        Dictionary with a list of active weather alerts
    """
    # Convert string to City enum
    city_enum = City(city)

    # Simulated alerts
    alerts = {
        City.NEW_YORK: [],
        City.LONDON: ["Heavy rain warning until 6 PM"],
        City.TOKYO: [],
        City.PARIS: [],
        City.SYDNEY: ["UV index very high"],
    }
    return {"content":{"alerts": alerts.get(city_enum, [])}}


@traced(name="main")
async def main(input: WeatherInput) -> WeatherOutput:
    """Main weather agent that orchestrates different weather tools.

    This agent demonstrates multiple tool calls in sequence. Each tool invocation
    creates its own span with tool.name set, allowing trajectory evaluation to
    extract the complete sequence of tool calls.

    Example trace for "get_weather" action:
        1. Span: tool.name="get_temperature", input={"city": "New York"}, output={"temperature": 72.5, ...}
        2. Span: tool.name="get_weather_condition", input={"city": "New York"}, output={"condition": "sunny"}
        3. Span: tool.name="get_humidity", input={"city": "New York"}, output={"humidity": 60}
    """
    city = input.city.value  # Get string value from enum

    # Multiple tool calls - each creates its own span with tool.name attribute
    temp_data = await get_temperature(city)
    condition_data = await get_weather_condition(city)
    humidity_data = await get_humidity(city)

    forecast = None
    alerts = None

    # Conditional tool calls based on action - each also creates its own span
    # For "get_forecast": 4 total tool spans (temp, condition, humidity, forecast)
    # For "get_alerts": 4 total tool spans (temp, condition, humidity, alerts)
    # For "get_weather": 3 total tool spans (temp, condition, humidity)
    if input.action == "get_forecast":
        forecast_data = await get_forecast(city)
        forecast = forecast_data["content"]["forecast"]
    elif input.action == "get_alerts":
        alerts_data = await get_weather_alerts(city)
        alerts = alerts_data["content"]["alerts"]
    elif input.action == "get_weather":
        # For simple weather requests, just return basic info
        pass

    return WeatherOutput(
        content=_WeatherOutputContent(
        city=city,
        temperature=temp_data["content"]["temperature"],
        condition=WeatherCondition(condition_data["content"]["condition"]),
        humidity=humidity_data["content"]["humidity"],
        forecast=forecast,
        alerts=alerts,
        )
    )
