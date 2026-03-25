"""Simple agent to test line-by-line evaluation.

This agent takes a list of items and outputs one result per line.
"""

from pydantic import BaseModel


class Input(BaseModel):
    """Input schema."""

    items: list[str]


class Output(BaseModel):
    """Output schema."""

    result: str


def main(input_data: Input) -> Output:
    """Process items and return one result per line.

    Args:
        input_data: Input containing list of items

    Returns:
        Output with one processed item per line
    """
    results = []
    for item in input_data.items:
        results.append(f"Item: {item}")

    return Output(result="\n".join(results))
