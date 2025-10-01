import random

from pydantic.dataclasses import dataclass
from enum import Enum

from uipath.tracing import traced
import logging

from uipath._cli._evals.mocks.mocks import mockable

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

@dataclass
class Wrapper:
    # Testing nested objects
    result: Operator

@traced()
<<<<<<< HEAD
@mockable()
def get_random_operator() -> Wrapper:
    """Get a random operator."""
    return Wrapper(result=random.choice([Operator.ADD, Operator.SUBTRACT, Operator.MULTIPLY, Operator.DIVIDE]))


@traced()
async def main(input: CalculatorInput) -> CalculatorOutput:
    if input.operator == Operator.RANDOM:
        operator = get_random_operator().result
    else:
        operator = input.operator
    match operator:
=======
def main(input: CalculatorInput) -> CalculatorOutput:
    result = 0.0
    match input.operator:
>>>>>>> d766fe8 (feat: format uipath eval output to show scores)
        case Operator.ADD: result = input.a + input.b
        case Operator.SUBTRACT: result = input.a - input.b
        case Operator.MULTIPLY: result = input.a * input.b
        case Operator.DIVIDE: result = input.a / input.b if input.b != 0.0 else 0.0
        case _: raise ValueError("Unknown operator")
    return CalculatorOutput(result=result)
