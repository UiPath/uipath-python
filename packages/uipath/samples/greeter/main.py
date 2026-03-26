"""Simple greeter function for testing input simulation."""

from pydantic.dataclasses import dataclass


@dataclass
class GreeterInput:
    """Input for the greeter function."""

    name: str
    greeting_style: str = "formal"


@dataclass
class GreeterOutput:
    """Output from the greeter function."""

    message: str
    recipient: str
    style: str


def main(input: GreeterInput) -> GreeterOutput:
    """Generate a greeting based on the name and style.

    Args:
        input: The greeter input containing name and greeting_style

    Returns:
        A GreeterOutput containing the greeting message
    """
    greetings = {
        "formal": f"Good day, {input.name}. It is a pleasure to meet you.",
        "casual": f"Hey {input.name}, what's up?",
        "enthusiastic": f"Wow! Hi {input.name}!! So great to see you!!!",
    }

    greeting = greetings.get(input.greeting_style, greetings["formal"])

    return GreeterOutput(
        message=greeting, recipient=input.name, style=input.greeting_style
    )
