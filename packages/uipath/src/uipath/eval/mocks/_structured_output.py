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
_DEFS_PREFIX = "#/$defs/"


def _inline_defs(
    schema: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Inline ``$defs``/``$ref`` into a self-contained schema.

    Nested Pydantic models and enums emit root ``$defs`` referenced by ``$ref``.
    The normalized gateway accepts those in ``response_format`` but not inside a
    tool's ``parameters``, so they are inlined here. Self-referential definitions
    cannot be inlined without looping; any ``$ref`` reached while its target is
    already on the current resolution path is left untouched and its definitions
    are returned so the caller can keep them reachable.

    Returns:
        A tuple of (inlined schema, leftover ``$defs`` needed for cyclic refs).
    """
    defs = schema.get("$defs", {})
    leftover: dict[str, Any] = {}

    def resolve(node: Any, active: frozenset[str]) -> Any:
        if isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str) and ref.startswith(_DEFS_PREFIX):
                name = ref[len(_DEFS_PREFIX) :]
                if name in defs and name not in active:
                    return resolve(defs[name], active | {name})
                # Cyclic or unknown ref: keep it and preserve its definition.
                if name in defs:
                    leftover[name] = defs[name]
                return dict(node)
            return {
                key: resolve(value, active)
                for key, value in node.items()
                if key != "$defs"
            }
        if isinstance(node, list):
            return [resolve(item, active) for item in node]
        return node

    root = {key: value for key, value in schema.items() if key != "$defs"}
    inlined = resolve(root, frozenset())
    return inlined, leftover


def build_response_tool(schema: dict[str, Any], description: str) -> dict[str, Any]:
    """Build a normalized-API function tool that wraps ``schema`` under ``response``.

    Tool-call arguments are always a JSON object, so an arbitrary output schema
    (which may be a scalar, array, or object) is nested under a single
    ``response`` property and unwrapped after the call. ``$defs``/``$ref`` are
    inlined so the tool parameters are self-contained, which the gateway requires
    for tool schemas (unlike ``response_format``).
    """
    response_schema, leftover_defs = _inline_defs(schema)
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {RESPONSE_KEY: response_schema},
        "required": [RESPONSE_KEY],
    }
    if leftover_defs:
        parameters["$defs"] = leftover_defs

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
