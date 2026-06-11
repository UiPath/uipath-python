"""Unit tests for the provider-agnostic structured-output helpers."""

import json
from types import SimpleNamespace
from typing import Any

import pytest

from uipath.eval.mocks._structured_output import (
    RESPONSE_KEY,
    RESPONSE_TOOL_NAME,
    build_response_tool,
    extract_response,
    generate_structured_output,
)


def _response(message: SimpleNamespace | None) -> SimpleNamespace:
    choices = [] if message is None else [SimpleNamespace(message=message)]
    return SimpleNamespace(choices=choices)


class _FakeLLM:
    """Records chat_completions calls and replays queued responses in order."""

    def __init__(self, responses: list[Any]):
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    async def chat_completions(self, messages: Any, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        nxt = self._responses.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt


def test_build_response_tool_wraps_schema_under_response():
    tool = build_response_tool({"type": "string"}, description="desc")
    assert tool["name"] == RESPONSE_TOOL_NAME
    assert tool["description"] == "desc"
    assert tool["parameters"]["properties"][RESPONSE_KEY] == {"type": "string"}
    assert tool["parameters"]["required"] == [RESPONSE_KEY]


def test_build_response_tool_inlines_refs_into_self_contained_schema():
    # Nested Pydantic models / enums emit $defs + $ref. The normalized gateway
    # accepts $ref/$defs in response_format but NOT in a tool's parameters, so the
    # schema must be inlined into a self-contained form (no $ref/$defs anywhere).
    operator_def = {"enum": ["+", "-", "*", "/"], "type": "string"}
    item_def = {"type": "object", "properties": {"sku": {"type": "string"}}}
    schema = {
        "type": "object",
        "properties": {
            "operator": {"$ref": "#/$defs/Operator"},
            "items": {"type": "array", "items": {"$ref": "#/$defs/Item"}},
        },
        "required": ["operator"],
        "$defs": {"Operator": operator_def, "Item": item_def},
    }

    tool = build_response_tool(schema, description="d")
    params = tool["parameters"]

    blob = json.dumps(params)
    assert "$ref" not in blob
    assert "$defs" not in blob

    response = params["properties"][RESPONSE_KEY]
    assert response["properties"]["operator"] == operator_def
    assert response["properties"]["items"]["items"] == item_def
    # caller's schema is not mutated
    assert "$defs" in schema


def test_build_response_tool_keeps_defs_for_cyclic_refs():
    # Self-referential schemas can't be fully inlined; keep $defs hoisted so the
    # remaining $ref still resolves rather than infinite-looping.
    node_def = {
        "type": "object",
        "properties": {"child": {"$ref": "#/$defs/Node"}},
    }
    schema = {
        "type": "object",
        "properties": {"root": {"$ref": "#/$defs/Node"}},
        "$defs": {"Node": node_def},
    }

    tool = build_response_tool(schema, description="d")
    params = tool["parameters"]

    assert "$defs" in params
    assert "$ref" in json.dumps(params)
    # the caller's schema dict is not mutated
    assert "$defs" in schema


def test_extract_response_returns_wrapped_value():
    message = SimpleNamespace(
        content=None,
        tool_calls=[SimpleNamespace(arguments={RESPONSE_KEY: {"a": 1}})],
    )
    assert extract_response(_response(message)) == {"a": 1}


def test_extract_response_raises_when_no_choices():
    with pytest.raises(ValueError, match="no choices"):
        extract_response(_response(None))


def test_extract_response_raises_when_no_tool_calls():
    # Non-OpenAI text response without a tool call: surface a clear error.
    message = SimpleNamespace(content="not a tool call", tool_calls=None)
    with pytest.raises(ValueError, match="no tool calls"):
        extract_response(_response(message))


def test_extract_response_raises_when_response_key_missing():
    message = SimpleNamespace(
        content=None, tool_calls=[SimpleNamespace(arguments={"other": 1})]
    )
    with pytest.raises(ValueError, match=RESPONSE_KEY):
        extract_response(_response(message))


@pytest.mark.asyncio
async def test_generate_structured_output_prefers_response_format_content():
    # OpenAI returns content via response_format; no fallback call is made.
    llm = _FakeLLM([_response(SimpleNamespace(content='{"a": 1}', tool_calls=None))])
    result = await generate_structured_output(
        llm,
        [{"role": "user", "content": "x"}],
        schema={"type": "object"},
        response_format_name="OutputSchema",
        description="d",
        completion_kwargs={},
    )
    assert result == {"a": 1}
    assert len(llm.calls) == 1
    assert "response_format" in llm.calls[0]
    assert "tools" not in llm.calls[0]


@pytest.mark.asyncio
async def test_generate_structured_output_falls_back_on_prose_content():
    # Claude on the normalized gateway answers response_format requests with
    # plain prose (e.g. "Tokyo") — truthy but not JSON. Must fall back to tools
    # instead of raising JSONDecodeError (AE-1646).
    llm = _FakeLLM(
        [
            _response(SimpleNamespace(content="Tokyo", tool_calls=None)),
            _response(
                SimpleNamespace(
                    content=None,
                    tool_calls=[SimpleNamespace(arguments={RESPONSE_KEY: {"a": 1}})],
                )
            ),
        ]
    )
    result = await generate_structured_output(
        llm,
        [{"role": "user", "content": "x"}],
        schema={"type": "object"},
        response_format_name="OutputSchema",
        description="d",
        completion_kwargs={},
    )
    assert result == {"a": 1}
    assert len(llm.calls) == 2
    assert "tools" in llm.calls[1]


@pytest.mark.asyncio
async def test_generate_structured_output_falls_back_on_empty_content():
    # Non-OpenAI: response_format yields empty content -> fall back to tool call.
    llm = _FakeLLM(
        [
            _response(SimpleNamespace(content=None, tool_calls=None)),
            _response(
                SimpleNamespace(
                    content=None,
                    tool_calls=[SimpleNamespace(arguments={RESPONSE_KEY: {"a": 1}})],
                )
            ),
        ]
    )
    result = await generate_structured_output(
        llm,
        [{"role": "user", "content": "x"}],
        schema={"type": "object"},
        response_format_name="OutputSchema",
        description="d",
        completion_kwargs={},
    )
    assert result == {"a": 1}
    assert len(llm.calls) == 2
    assert "response_format" in llm.calls[0]
    assert "tools" in llm.calls[1] and "tool_choice" in llm.calls[1]


@pytest.mark.asyncio
async def test_generate_structured_output_falls_back_when_response_format_raises():
    # A provider that rejects response_format outright still gets a tool fallback.
    llm = _FakeLLM(
        [
            RuntimeError("response_format unsupported"),
            _response(
                SimpleNamespace(
                    content=None,
                    tool_calls=[SimpleNamespace(arguments={RESPONSE_KEY: "ok"})],
                )
            ),
        ]
    )
    result = await generate_structured_output(
        llm,
        [{"role": "user", "content": "x"}],
        schema={"type": "string"},
        response_format_name="OutputSchema",
        description="d",
        completion_kwargs={},
    )
    assert result == "ok"
    assert len(llm.calls) == 2


def test_build_response_tool_merges_ref_sibling_keys():
    # Pydantic can emit sibling keys (e.g. description) next to $ref; they
    # must survive inlining since they guide the LLM.
    schema = {
        "type": "object",
        "properties": {
            "op": {"$ref": "#/$defs/Op", "description": "the operator to use"}
        },
        "$defs": {"Op": {"type": "string", "enum": ["+", "-"]}},
    }
    tool = build_response_tool(schema, description="d")
    op = tool["parameters"]["properties"][RESPONSE_KEY]["properties"]["op"]
    assert op == {
        "type": "string",
        "enum": ["+", "-"],
        "description": "the operator to use",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "model",
    [
        "anthropic.claude-sonnet-4-5-20250929-v1:0",
        "claude-haiku-4-5",
        "gemini-2.5-pro",
    ],
)
async def test_non_openai_models_use_tool_call_directly(model: str):
    # Claude/Gemini don't honor response_format on the normalized gateway, so
    # their strategies skip it entirely: a single forced tool call.
    llm = _FakeLLM(
        [
            _response(
                SimpleNamespace(
                    content=None,
                    tool_calls=[SimpleNamespace(arguments={RESPONSE_KEY: "ok"})],
                )
            )
        ]
    )
    result = await generate_structured_output(
        llm,
        [{"role": "user", "content": "x"}],
        schema={"type": "string"},
        response_format_name="OutputSchema",
        description="d",
        completion_kwargs={"model": model},
    )
    assert result == "ok"
    assert len(llm.calls) == 1
    assert "tools" in llm.calls[0] and "tool_choice" in llm.calls[0]
    assert "response_format" not in llm.calls[0]


@pytest.mark.asyncio
async def test_openai_models_prefer_response_format():
    llm = _FakeLLM([_response(SimpleNamespace(content='{"a": 1}', tool_calls=None))])
    result = await generate_structured_output(
        llm,
        [{"role": "user", "content": "x"}],
        schema={"type": "object"},
        response_format_name="OutputSchema",
        description="d",
        completion_kwargs={"model": "gpt-4.1-mini-2025-04-14"},
    )
    assert result == {"a": 1}
    assert len(llm.calls) == 1
    assert "response_format" in llm.calls[0]
