"""
Calculator Coded Agent
Performs mathematical operations on two numbers with validation
"""

from langgraph.graph import START, StateGraph, END
from pydantic import BaseModel, Field, field_validator
from typing import Union


class Input(BaseModel):
    """Input schema for calculator agent"""
    a: Union[int, float] = Field(..., description="First number")
    b: Union[int, float] = Field(..., description="Second number")
    operator: str = Field(..., description="Mathematical operator: +, -, *, /, **, %, //")

    @field_validator('a', 'b')
    @classmethod
    def validate_number(cls, v):
        """Ensure inputs are valid numbers"""
        if not isinstance(v, (int, float)):
            raise ValueError(f"Value must be a number, got {type(v).__name__}")
        return v

    @field_validator('operator')
    @classmethod
    def validate_operator(cls, v):
        """Ensure operator is supported"""
        valid_operators = ['+', '-', '*', '/', '**', '%', '//']
        if v not in valid_operators:
            raise ValueError(f"Operator must be one of {valid_operators}, got '{v}'")
        return v


class State(BaseModel):
    """Internal state for the calculator agent"""
    a: Union[int, float]
    b: Union[int, float]
    operator: str
    result: Union[int, float, str] = ""
    error: str = ""


class Output(BaseModel):
    """Output schema for calculator agent"""
    result: Union[int, float, str] = Field(..., description="Result of the operation or error message")
    operation: str = Field(..., description="The operation that was performed")
    success: bool = Field(..., description="Whether the operation was successful")


def validate_inputs(state: State) -> State:
    """Validate that inputs are numbers and operator is valid"""
    # Validation is handled by Pydantic, so if we get here, inputs are valid
    return state


def perform_operation(state: State) -> State:
    """Perform the mathematical operation based on the operator"""
    try:
        a = state.a
        b = state.b
        operator = state.operator

        # Perform the operation using match-case
        match operator:
            case '+':
                result = a + b
            case '-':
                result = a - b
            case '*':
                result = a * b
            case '/':
                if b == 0:
                    return State(
                        a=a, b=b, operator=operator,
                        result="", error="Division by zero is not allowed"
                    )
                result = a / b
            case '**':
                result = a ** b
            case '%':
                if b == 0:
                    return State(
                        a=a, b=b, operator=operator,
                        result="", error="Modulo by zero is not allowed"
                    )
                result = a % b
            case '//':
                if b == 0:
                    return State(
                        a=a, b=b, operator=operator,
                        result="", error="Floor division by zero is not allowed"
                    )
                result = a // b
            case _:
                return State(
                    a=a, b=b, operator=operator,
                    result="", error=f"Unsupported operator: {operator}"
                )

        return State(a=a, b=b, operator=operator, result=result, error="")

    except Exception as e:
        return State(
            a=state.a, b=state.b, operator=state.operator,
            result="", error=f"Error performing operation: {str(e)}"
        )


def create_output(state: State) -> Output:
    """Create the output based on the operation result"""
    operation = f"{state.a} {state.operator} {state.b}"

    if state.error:
        return Output(
            result=state.error,
            operation=operation,
            success=False
        )

    return Output(
        result=state.result,
        operation=f"{operation} = {state.result}",
        success=True
    )


# Build the graph
builder = StateGraph(State, input=Input, output=Output)

# Add nodes
builder.add_node("validate", validate_inputs)
builder.add_node("calculate", perform_operation)
builder.add_node("output", create_output)

# Add edges
builder.add_edge(START, "validate")
builder.add_edge("validate", "calculate")
builder.add_edge("calculate", "output")
builder.add_edge("output", END)

# Compile the graph
graph = builder.compile()
