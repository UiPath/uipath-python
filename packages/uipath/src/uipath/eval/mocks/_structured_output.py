"""Provider-agnostic structured output for the eval mockers.

The normalized LLM Gateway honors OpenAI-style ``response_format`` (json_schema)
only for OpenAI models — and does so reliably, including native ``$defs``
support. Non-OpenAI providers (Anthropic/Claude via Bedrock, Gemini) return such
requests with ``choices[0].message.content`` empty/None, which breaks JSON
parsing. Function calling is honored across providers but is less reliable for
OpenAI on some schemas, so it is used only as a fallback: prefer
``response_format`` and fall back to a forced tool call when the content comes
back empty.
"""

import json
import logging
from typing import Any

from uipath.platform.chat.llm_gateway import RequiredToolChoice

RESPONSE_TOOL_NAME = "submit_tool_response"
RESPONSE_KEY = "response"
_DEFS_PREFIX = "#/$defs/"

logger = logging.getLogger(__name__)


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


async def generate_structured_output(
    llm: Any,
    messages: list[dict[str, str]],
    *,
    schema: dict[str, Any],
    response_format_name: str,
    description: str,
    completion_kwargs: dict[str, Any],
) -> Any:
    """Generate structured output that works across all model providers.

    Prefers ``response_format`` (json_schema) — honored reliably by OpenAI with
    native ``$defs`` support. When the provider returns empty content (the
    non-OpenAI failure mode, e.g. Claude/Bedrock), falls back to a forced tool
    call, which is honored across providers.
    """
    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": response_format_name,
            "strict": False,
            "schema": schema,
        },
    }

    content: str | None = None
    try:
        rf_response = await llm.chat_completions(
            messages, response_format=response_format, **completion_kwargs
        )
        choices = getattr(rf_response, "choices", None)
        if choices:
            content = choices[0].message.content
    except Exception as e:
        # Some providers reject response_format outright; fall back to tools.
        logger.info("response_format path failed, falling back to tools: %s", e)

    if content:
        return json.loads(content)

    tool = build_response_tool(schema, description)
    tc_response = await llm.chat_completions(
        messages,
        tools=[tool],
        tool_choice=RequiredToolChoice(),
        **completion_kwargs,
    )
    return extract_response(tc_response)
