"""Provider-aware structured output for the eval mockers.

The normalized LLM Gateway handles OpenAI-style ``response_format``
(json_schema) differently per provider — live-verified against the gateway:

- **OpenAI**: honors ``response_format`` and returns valid JSON content,
  including native ``$defs`` support.
- **Anthropic (Claude)**: ignores it and answers with plain prose content.
- **Gemini**: returns empty content.

Forced function calling works across all three providers, so each provider
gets a small strategy class: OpenAI prefers ``response_format`` (more reliable
for it on some schemas) with a tool-call fallback; Claude and Gemini go
straight to the forced tool call; unknown providers try ``response_format``
first and fall back.
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
    tool's ``parameters``, so they are inlined here. Sibling keys on a ``$ref``
    node (e.g. a field ``description``) are merged over the inlined definition.
    Self-referential definitions cannot be inlined without looping; any ``$ref``
    reached while its target is already on the current resolution path is left
    untouched and its definitions are returned so the caller can keep them
    reachable.

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
                    resolved = resolve(defs[name], active | {name})
                    siblings = {
                        key: resolve(value, active)
                        for key, value in node.items()
                        if key not in ("$ref", "$defs")
                    }
                    if isinstance(resolved, dict):
                        return {**resolved, **siblings}
                    return resolved
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


class ToolCallStructuredOutput:
    """Structured output via a forced tool call — works on every provider."""

    async def generate(
        self,
        llm: Any,
        messages: list[dict[str, str]],
        *,
        schema: dict[str, Any],
        response_format_name: str,
        description: str,
        completion_kwargs: dict[str, Any],
    ) -> Any:
        """Force a tool call wrapping ``schema`` and unwrap its arguments."""
        tool = build_response_tool(schema, description)
        response = await llm.chat_completions(
            messages,
            tools=[tool],
            tool_choice=RequiredToolChoice(),
            **completion_kwargs,
        )
        return extract_response(response)


class ResponseFormatStructuredOutput(ToolCallStructuredOutput):
    """Prefer ``response_format`` (json_schema); fall back to a forced tool call.

    The fallback fires when the provider rejects the request, returns empty
    content, or returns content that is not valid JSON (Claude's behavior on
    the normalized gateway is to answer with plain prose).
    """

    async def generate(
        self,
        llm: Any,
        messages: list[dict[str, str]],
        *,
        schema: dict[str, Any],
        response_format_name: str,
        description: str,
        completion_kwargs: dict[str, Any],
    ) -> Any:
        """Try ``response_format`` first, falling back to a forced tool call."""
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
            response = await llm.chat_completions(
                messages, response_format=response_format, **completion_kwargs
            )
            choices = getattr(response, "choices", None)
            if choices:
                content = choices[0].message.content
        except Exception as e:
            logger.info("response_format path failed, falling back to tools: %s", e)

        if content:
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                logger.info(
                    "response_format content was not JSON, falling back to tools"
                )

        return await super().generate(
            llm,
            messages,
            schema=schema,
            response_format_name=response_format_name,
            description=description,
            completion_kwargs=completion_kwargs,
        )


class OpenAIStructuredOutput(ResponseFormatStructuredOutput):
    """OpenAI honors ``response_format`` natively (including ``$defs``)."""


class AnthropicStructuredOutput(ToolCallStructuredOutput):
    """Claude answers ``response_format`` with prose; go straight to tools."""


class GeminiStructuredOutput(ToolCallStructuredOutput):
    """Gemini returns empty content for ``response_format``; go straight to tools."""


def _strategy_for_model(model: str | None) -> ToolCallStructuredOutput:
    name = (model or "").lower()
    if "claude" in name or name.startswith("anthropic"):
        return AnthropicStructuredOutput()
    if "gemini" in name:
        return GeminiStructuredOutput()
    if name.startswith(("gpt", "o1", "o3", "o4")):
        return OpenAIStructuredOutput()
    # Unknown providers: try response_format, fall back to tools.
    return ResponseFormatStructuredOutput()


async def generate_structured_output(
    llm: Any,
    messages: list[dict[str, str]],
    *,
    schema: dict[str, Any],
    response_format_name: str,
    description: str,
    completion_kwargs: dict[str, Any],
) -> Any:
    """Generate structured output using the strategy for the requested model."""
    strategy = _strategy_for_model(completion_kwargs.get("model"))
    return await strategy.generate(
        llm,
        messages,
        schema=schema,
        response_format_name=response_format_name,
        description=description,
        completion_kwargs=completion_kwargs,
    )
