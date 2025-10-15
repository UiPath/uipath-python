import logging
import random
from enum import Enum

from pydantic.dataclasses import dataclass

from uipath.eval.mocks import ExampleCall, mockable
from uipath.tracing import traced

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

GET_RANDOM_OPERATOR_EXAMPLES = [ExampleCall(id="example", input="{}", output="{\"result\": \"*\"}")]

@traced()
@mockable(example_calls=GET_RANDOM_OPERATOR_EXAMPLES)
async def get_random_operator() -> Wrapper:
    """Get a random operator."""
    return Wrapper(result=random.choice([Operator.ADD, Operator.SUBTRACT, Operator.MULTIPLY, Operator.DIVIDE]))

@traced(name="track_operator")
def track_operator(operator: Operator):
    pass

@traced()
async def main(input: CalculatorInput) -> CalculatorOutput:
    if input.operator == Operator.RANDOM:
        operator = (await get_random_operator()).result
    else:
        operator = input.operator
    track_operator(operator)
    match operator:
        case Operator.ADD: result = input.a + input.b
        case Operator.SUBTRACT: result = input.a - input.b
        case Operator.MULTIPLY: result = input.a * input.b
        case Operator.DIVIDE: result = input.a / input.b if input.b != 0.0 else 0.0
        case _: raise ValueError("Unknown operator")
    return CalculatorOutput(result=result)
