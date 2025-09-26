import random

from pydantic.dataclasses import dataclass
from enum import Enum

from uipath.tracing import traced
import logging

from uipath.eval.mocks.mocks import mockable

logger = logging.getLogger(__name__)

class Operator(Enum):
    ADD = "+"
    SUBTRACT = "-"
    MULTIPLY = "*"
    DIVIDE = "/"
    RANDOM = "random"

@dataclass
class CalculatorInput:
    a: float
    b: float
    operator: Operator

@dataclass
class CalculatorOutput:
    result: float

@traced()
@mockable()
def get_random_operator() -> Operator:
    """Get a random operator."""
    return random.choice([Operator.ADD, Operator.SUBTRACT, Operator.MULTIPLY, Operator.DIVIDE])


@traced()
async def main(input: CalculatorInput) -> CalculatorOutput:
    if input.operator == Operator.RANDOM:
        operator = get_random_operator()
    else:
        operator = input.operator
    match operator:
        case Operator.ADD: result = input.a + input.b
        case Operator.SUBTRACT: result = input.a - input.b
        case Operator.MULTIPLY: result = input.a * input.b
        case Operator.DIVIDE: result = input.a / input.b if input.b != 0.0 else 0.0
        case _: raise ValueError("Unknown operator")
    return CalculatorOutput(result=result)
