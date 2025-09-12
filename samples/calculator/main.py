from pydantic.dataclasses import dataclass
from enum import Enum

from uipath.tracing import traced
import logging

logger = logging.getLogger(__name__)

class Operator(Enum):
    ADD = "+"
    SUBTRACT = "-"
    MULTIPLY = "*"
    DIVIDE = "/"

@dataclass
class CalculatorInput:
    a: float
    b: float
    operator: Operator

@dataclass
class CalculatorOutput:
    result: float

# use InputTriggerEventArgs when called by UiPath EventTriggers
@traced()
def main(input: CalculatorInput) -> CalculatorOutput:
    result = 0
    match input.operator:
        case Operator.ADD: result = input.a + input.b
        case Operator.SUBTRACT: result = input.a - input.b
        case Operator.MULTIPLY: result = input.a * input.b
        case Operator.DIVIDE: result = input.a / input.b if input.b != 0 else 0
    return CalculatorOutput(result=result)
