"""Unit tests for the provider-agnostic structured-output helpers."""

import json
from types import SimpleNamespace

import pytest

from uipath.eval.mocks._structured_output import (
    RESPONSE_KEY,
    RESPONSE_TOOL_NAME,
    build_response_tool,
    extract_response,
)


def _response(message: SimpleNamespace | None) -> SimpleNamespace:
    choices = [] if message is None else [SimpleNamespace(message=message)]
    return SimpleNamespace(choices=choices)


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
