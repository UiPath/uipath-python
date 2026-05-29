"""Provider-agnostic structured output via LLM function calling.

The normalized LLM Gateway honors OpenAI-style ``response_format`` (json_schema)
only for OpenAI models. Non-OpenAI providers (Anthropic/Claude via Bedrock,
Gemini) return such requests with ``choices[0].message.content`` empty/None,
which breaks JSON parsing. Function calling is honored across all providers, so
the mockers request structured output as a forced tool call and read the result
from the tool call's parsed arguments.
"""

from typing import Any

RESPONSE_TOOL_NAME = "submit_tool_response"
RESPONSE_KEY = "response"


def build_response_tool(schema: dict[str, Any], description: str) -> dict[str, Any]:
    """Build a normalized-API function tool that wraps ``schema`` under ``response``.

    Tool-call arguments are always a JSON object, so an arbitrary output schema
    (which may be a scalar, array, or object) is nested under a single
    ``response`` property and unwrapped after the call.

    Schemas from nested Pydantic models carry root ``$defs`` referenced by
    ``$ref`` values like ``#/$defs/Item``. Those ``$ref`` paths resolve from the
    parameters root, so ``$defs`` is hoisted there instead of being buried under
    ``response`` (which would leave the references dangling).
    """
    response_schema = dict(schema)
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {RESPONSE_KEY: response_schema},
        "required": [RESPONSE_KEY],
    }
    defs = response_schema.pop("$defs", None)
    if defs is not None:
        parameters["$defs"] = defs

    return {
        "name": RESPONSE_TOOL_NAME,
        "description": description,
        "parameters": parameters,
    }


def extract_response(response: Any) -> Any:
    """Extract the wrapped value from the forced tool call.

    Raises:
        ValueError: if the response carries no usable tool call or is missing the
            wrapped ``response`` key.
    """
    choices = getattr(response, "choices", None)
    if not choices:
        raise ValueError("LLM response contained no choices")

    message = choices[0].message
    tool_calls = getattr(message, "tool_calls", None)
    if not tool_calls:
        raise ValueError(
            f"LLM response contained no tool calls (content={message.content!r})"
        )

    arguments = tool_calls[0].arguments
    if RESPONSE_KEY not in arguments:
        raise ValueError(
            f"Tool call arguments missing '{RESPONSE_KEY}' key: {arguments}"
        )

    return arguments[RESPONSE_KEY]
