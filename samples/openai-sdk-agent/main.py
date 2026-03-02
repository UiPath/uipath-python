import asyncio

import dotenv
from agents import Agent, RawResponsesStreamEvent, Runner, trace
from openai.types.responses import ResponseContentPartDoneEvent, ResponseTextDeltaEvent
from pydantic import BaseModel

from uipath.tracing import traced

dotenv.load_dotenv()

"""
This example shows the handoffs/routing pattern adapted for UiPath coded agents.
The triage agent receives the first message, and then hands off to the appropriate
agent based on the language of the request. Responses are streamed to the user.

Based on: https://github.com/openai/openai-agents-python/blob/main/examples/agent_patterns/routing.py
"""


# Required Input/Output models for UiPath coded agents
class Input(BaseModel):
    """Input model for the routing agent."""

    message: str


class Output(BaseModel):
    """Output model for the routing agent."""

    response: str
    agent_used: str


# Define specialized agents for different languages
french_agent = Agent(
    name="french_agent",
    instructions="You only speak French",
)

spanish_agent = Agent(
    name="spanish_agent",
    instructions="You only speak Spanish",
)

english_agent = Agent(
    name="english_agent",
    instructions="You only speak English",
)

# Triage agent routes to appropriate language agent
triage_agent = Agent(
    name="triage_agent",
    instructions="Handoff to the appropriate agent based on the language of the request.",
    handoffs=[french_agent, spanish_agent, english_agent],
)


@traced(name="Language Routing Agent Main")
async def main(input_data: Input) -> Output:
    """Main function to run the language routing agent.

    Args:
        input_data: Input model with a message for the agent.

    Returns:
        Output: Result containing the agent's response and which agent was used.
    """
    print(f"\nProcessing message: {input_data.message}")

    with trace("Language Routing Agent"):
        # Run the agent with streaming
        result = Runner.run_streamed(
            triage_agent,
            input=[{"content": input_data.message, "role": "user"}],
        )

        # Collect the response
        response_parts = []
        async for event in result.stream_events():
            if not isinstance(event, RawResponsesStreamEvent):
                continue
            data = event.data
            if isinstance(data, ResponseTextDeltaEvent):
                print(data.delta, end="", flush=True)
                response_parts.append(data.delta)
            elif isinstance(data, ResponseContentPartDoneEvent):
                print()

        # Get the final response and agent used
        final_response = "".join(response_parts)
        agent_used = result.current_agent.name

    print(f"\n\nAgent used: {agent_used}")
    return Output(response=final_response, agent_used=agent_used)


if __name__ == "__main__":
    # Example usage with different languages:
    # 1. English message
    # asyncio.run(main(Input(message="Hello, how are you?")))

    # 2. French message
    # asyncio.run(main(Input(message="Bonjour, comment allez-vous?")))

    # 3. Spanish message
    asyncio.run(main(Input(message="Hola, ¿cómo estás?")))
