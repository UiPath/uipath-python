"""Weather forecast agent demonstrating per-component simulation.

This sample shows the new ``components`` simulation format where each tool
has its own simulation strategy and instructions, routed to the
simulate-component API instead of a local LLM.

Run with real tools (no weather API — returns hardcoded defaults):
    uipath run main -f input.json

Run with per-component simulation (routes each tool call to the API):
    uipath run main -f input.json --simulation "$(cat simulation.json)"
"""

from pydantic import BaseModel
from pydantic.dataclasses import dataclass

from uipath.eval.mocks import mockable
from uipath.tracing import traced

# ---------------------------------------------------------------------------
# Input / Output models
# ---------------------------------------------------------------------------


@dataclass
class WeatherInput:
    city: str
    days: int = 3


class CurrentWeather(BaseModel):
    city: str
    temperature: float  # Celsius
    condition: str
    humidity: int  # percent


class ForecastDay(BaseModel):
    date: str  # YYYY-MM-DD
    high: float
    low: float
    condition: str


class WeatherReport(BaseModel):
    current: CurrentWeather
    forecast: list[ForecastDay]
    summary: str


# ---------------------------------------------------------------------------
# Mockable tool functions
# ---------------------------------------------------------------------------


@traced(name="get_current_weather", span_type="tool")
@mockable()
async def get_current_weather(city: str) -> CurrentWeather:
    """Fetch current weather conditions for a city from an external weather API.

    Args:
        city: Name of the city (e.g. "London", "New York").

    Returns:
        CurrentWeather with temperature, condition, and humidity.
    """
    # Real implementation would call a weather API such as OpenWeatherMap.
    # Returns hardcoded defaults when not simulated.
    return CurrentWeather(city=city, temperature=20.0, condition="unknown", humidity=50)


@traced(name="get_forecast", span_type="tool")
@mockable()
async def get_forecast(city: str, days: int = 3) -> list[ForecastDay]:
    """Retrieve a multi-day weather forecast for a city.

    Args:
        city: Name of the city.
        days: Number of forecast days to retrieve (default: 3).

    Returns:
        List of ForecastDay objects, one per requested day.
    """
    # Real implementation would call a forecast API.
    # Returns an empty list when not simulated.
    return []


# ---------------------------------------------------------------------------
# Agent entry point
# ---------------------------------------------------------------------------


@traced(name="main")
async def main(input: WeatherInput) -> WeatherReport:
    """Fetch current weather and forecast for a city and produce a report.

    Args:
        input: WeatherInput with city name and number of forecast days.

    Returns:
        WeatherReport combining current conditions, forecast, and a summary.
    """
    current = await get_current_weather(input.city)
    forecast = await get_forecast(input.city, input.days)

    issues = []
    if current.humidity > 80:
        issues.append("high humidity")
    if current.temperature < 0:
        issues.append("freezing temperatures")

    alert = f" Alerts: {', '.join(issues)}." if issues else ""
    summary = (
        f"{input.city}: {current.temperature}°C, {current.condition}."
        f" {len(forecast)}-day forecast available.{alert}"
    )
    return WeatherReport(current=current, forecast=forecast, summary=summary)
