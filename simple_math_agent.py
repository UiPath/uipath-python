import dataclasses
from typing import Dict, Any


@dataclasses.dataclass
class MathAgentInput:
    """Input data structure for the math agent.

    Attributes:
        first_number (int): The first integer to add.
        second_number (int): The second integer to add.
    """

    first_number: int
    second_number: int


def add_numbers(first: int, second: int) -> Dict[str, Any]:
    """Adds two numbers together.

    Args:
        first (int): The first number to add.
        second (int): The second number to add.

    Returns:
        Dict[str, Any]: Dictionary containing the calculation result.
    """
    result = first + second
    return {
        "operation": "addition",
        "first_number": first,
        "second_number": second,
        "result": result,
        "calculation": f"{first} + {second} = {result}"
    }


async def main(input: MathAgentInput) -> str:
    """Main entry point for the math agent.

    Args:
        input (MathAgentInput): The input containing two integers to sum.

    Returns:
        str: The agent's response with the calculation result.
    """
    # Perform the calculation
    calculation_result = add_numbers(input.first_number, input.second_number)
    
    # Format the response message
    response = (
        f"Math Agent Calculation:\n"
        f"Operation: {calculation_result['operation']}\n"
        f"First Number: {calculation_result['first_number']}\n"
        f"Second Number: {calculation_result['second_number']}\n"
        f"Result: {calculation_result['result']}\n"
        f"Calculation: {calculation_result['calculation']}"
    )
    
    return response 