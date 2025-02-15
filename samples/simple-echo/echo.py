from dataclasses import dataclass
from typing import Annotated, Optional

from uipath_sdk.package._arguments import InputArgument, OutputArgument


@dataclass
class EchoInput:
    message: Annotated[str, InputArgument()]
    repeat: Annotated[Optional[int], InputArgument()] = 1
    prefix: Annotated[Optional[str], InputArgument()] = None


@dataclass
class EchoOutput:
    original_input: Annotated[EchoInput, OutputArgument()]
    result: Annotated[str, OutputArgument()]


def main(input_data: dict) -> dict:
    # Parse input into typed class
    echo_input = EchoInput(
        message=input_data.get("message", ""),
        repeat=input_data.get("repeat", 1),
        prefix=input_data.get("prefix"),
    )

    # Process the input
    result = []
    for _ in range(echo_input.repeat):
        line = echo_input.message
        if echo_input.prefix:
            line = f"{echo_input.prefix}: {line}"
        result.append(line)

    # Create and return output
    output = EchoOutput(original_input=echo_input, result="\n".join(result))

    return {
        "input": {
            "message": output.original_input.message,
            "repeat": output.original_input.repeat,
            "prefix": output.original_input.prefix,
        },
        "output": output.result,
    }
