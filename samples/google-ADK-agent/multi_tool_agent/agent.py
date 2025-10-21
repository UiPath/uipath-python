import dataclasses
import datetime
from typing import Dict
from zoneinfo import ZoneInfo

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part


def get_weather(city: str) -> Dict[str, str]:
    """Retrieves the current weather report for a specified city.

    Args:
        city (str): The name of the city for which to retrieve the weather report.

    Returns:
        Dict[str, str]: Dictionary containing status and result or error message.
    """
    if city.lower() == "new york":
        return {
            "status": "success",
            "report": (
                "The weather in New York is sunny with a temperature of 25 degrees"
                " Celsius (77 degrees Fahrenheit)."
            ),
        }
    else:
        return {
            "status": "error",
            "error_message": f"Weather information for '{city}' is not available.",
        }


def get_current_time(city: str) -> Dict[str, str]:
    """Returns the current time in a specified city.

    Args:
        city (str): The name of the city for which to retrieve the current time.

    Returns:
        Dict[str, str]: Dictionary containing status and result or error message.
    """
    if city.lower() == "new york":
        tz_identifier = "America/New_York"
    else:
        return {
            "status": "error",
            "error_message": (f"Sorry, I don't have timezone information for {city}."),
        }

    tz = ZoneInfo(tz_identifier)
    now = datetime.datetime.now(tz)
    report = f"The current time in {city} is {now.strftime('%Y-%m-%d %H:%M:%S %Z%z')}"
    return {"status": "success", "report": report}


root_agent = Agent(
    name="weather_time_agent",
    model="gemini-1.5-flash",
    description=("Agent to answer questions about the time and weather in a city."),
    instruction=(
        "You are a helpful agent who can answer user questions about the time and weather in a city."
    ),
    tools=[get_weather, get_current_time],
)


@dataclasses.dataclass
class AgentInput:
    """Input data structure for the agent.

    Attributes:
        query (str): The user's query string.
    """

    query: str


def configure_ssl_context() -> None:
    """Configure SSL context with proper certificate paths."""
    import os
    import ssl

    default_paths = ssl.get_default_verify_paths()
    if default_paths.cafile:
        os.environ["SSL_CERT_FILE"] = default_paths.cafile
    if not os.getenv("SSL_CERT_DIR", None):
        os.environ["SSL_CERT_DIR"] = default_paths.capath or "/etc/ssl/certs"


async def main(input: AgentInput) -> str:
    """Main entry point for the agent.

    Args:
        input (AgentInput): The input containing the user's query.

    Returns:
        str: The agent's response to the query.
    """
    user_id = "test_user"
    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name="multi-tool-agent", user_id=user_id
    )
    configure_ssl_context()

    runner = Runner(
        app_name=session.app_name,
        agent=root_agent,
        session_service=session_service,
    )
    content = Content(parts=[Part(text=input.query)], role="user")
    output = ""
    async for event in runner.run_async(
        new_message=content,
        user_id=user_id,
        session_id=session.id,
    ):
        if event.content and event.content.parts:
            if text := "".join(part.text or "" for part in event.content.parts):
                output = text
    return output
