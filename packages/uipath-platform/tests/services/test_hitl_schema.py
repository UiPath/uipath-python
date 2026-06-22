"""Unit tests for the HITL dynamic schema types and generator."""

import json

import pytest
from pydantic import BaseModel, Field

from uipath.platform.common import CreateEscalation, CreateTask
from uipath.platform.hitl import (
    HitlFieldDirection,
    HitlFieldType,
    HitlSchema,
    HitlSchemaField,
    HitlSchemaOutcome,
    pydantic_to_hitl_schema,
)
from uipath.platform.resume_triggers._protocol import _schema_key


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _Inputs(BaseModel):
    text: str = Field(title="Text")
    count: int = Field(default=0, title="Count")
    active: bool = Field(default=True, title="Active")


class _Outputs(BaseModel):
    decision: str = Field(default="", title="Decision")
    notes: str | None = Field(default=None, title="Notes")


# ---------------------------------------------------------------------------
# HitlSchema wire format
# ---------------------------------------------------------------------------


def test_to_wire_format_serialises_enums_as_strings():
    schema = HitlSchema(
        title="Test",
        fields=[
            HitlSchemaField(
                id="f1",
                label="F1",
                type=HitlFieldType.INTEGER,
                direction=HitlFieldDirection.OUTPUT,
            )
        ],
        outcomes=[HitlSchemaOutcome(id="approve", label="Approve")],
    )
    wire = schema.to_wire_format()
    assert wire["fields"][0]["type"] == "integer"
    assert wire["fields"][0]["direction"] == "output"
    assert wire["outcomes"][0]["id"] == "approve"


def test_to_wire_format_excludes_none_fields():
    field = HitlSchemaField(id="x", type=HitlFieldType.STRING, direction=HitlFieldDirection.INPUT)
    schema = HitlSchema(fields=[field])
    wire = schema.to_wire_format()
    # 'label' and 'required' are None → excluded
    assert "label" not in wire["fields"][0]
    assert "required" not in wire["fields"][0]
    # 'title' and 'id' at top level are None/missing → excluded
    assert "title" not in wire
    assert "id" not in wire


# ---------------------------------------------------------------------------
# pydantic_to_hitl_schema
# ---------------------------------------------------------------------------


def test_input_fields_have_input_direction():
    schema = pydantic_to_hitl_schema(input_model=_Inputs)
    directions = {f.id: f.direction for f in schema.fields}
    assert all(d == HitlFieldDirection.INPUT for d in directions.values())


def test_output_fields_have_output_direction():
    schema = pydantic_to_hitl_schema(output_model=_Outputs)
    directions = {f.id: f.direction for f in schema.fields}
    assert all(d == HitlFieldDirection.OUTPUT for d in directions.values())


def test_field_ids_match_python_names():
    schema = pydantic_to_hitl_schema(input_model=_Inputs)
    ids = {f.id for f in schema.fields}
    assert ids == {"text", "count", "active"}


def test_field_ids_use_alias_when_set():
    class AliasModel(BaseModel):
        guardrail_name: str = Field(alias="GuardrailName", default="")

    schema = pydantic_to_hitl_schema(input_model=AliasModel)
    assert schema.fields[0].id == "GuardrailName"


def test_type_mapping():
    schema = pydantic_to_hitl_schema(input_model=_Inputs)
    types = {f.id: f.type for f in schema.fields}
    assert types["text"] == HitlFieldType.STRING
    assert types["count"] == HitlFieldType.INTEGER
    assert types["active"] == HitlFieldType.BOOLEAN


def test_optional_field_maps_to_inner_type():
    schema = pydantic_to_hitl_schema(output_model=_Outputs)
    types = {f.id: f.type for f in schema.fields}
    # notes: str | None → STRING
    assert types["notes"] == HitlFieldType.STRING


def test_default_outcomes():
    schema = pydantic_to_hitl_schema(input_model=_Inputs)
    assert [o.id for o in schema.outcomes] == ["approve", "reject"]
    assert [o.label for o in schema.outcomes] == ["Approve", "Reject"]


def test_custom_outcomes():
    schema = pydantic_to_hitl_schema(outcomes=["Yes", "No", "Maybe"])
    assert [o.id for o in schema.outcomes] == ["yes", "no", "maybe"]


def test_title_propagates():
    schema = pydantic_to_hitl_schema(title="My Form")
    assert schema.title == "My Form"


def test_combined_input_and_output():
    schema = pydantic_to_hitl_schema(input_model=_Inputs, output_model=_Outputs)
    input_ids = {f.id for f in schema.fields if f.direction == HitlFieldDirection.INPUT}
    output_ids = {f.id for f in schema.fields if f.direction == HitlFieldDirection.OUTPUT}
    assert input_ids == {"text", "count", "active"}
    assert output_ids == {"decision", "notes"}


def test_required_field_is_true_for_mandatory():
    # 'text' has no default → required
    schema = pydantic_to_hitl_schema(input_model=_Inputs)
    field_map = {f.id: f for f in schema.fields}
    assert field_map["text"].required is True
    # 'count' has default → not required (None in schema)
    assert field_map["count"].required is None


def test_output_fields_never_required():
    schema = pydantic_to_hitl_schema(output_model=_Outputs)
    for f in schema.fields:
        assert f.required is None


# ---------------------------------------------------------------------------
# CreateTask.hitl_schema field
# ---------------------------------------------------------------------------


def test_create_task_accepts_hitl_schema():
    schema = pydantic_to_hitl_schema(input_model=_Inputs)
    task = CreateTask(title="T", hitl_schema=schema)
    assert task.hitl_schema is schema


def test_create_task_hitl_schema_defaults_to_none():
    task = CreateTask(title="T")
    assert task.hitl_schema is None


def test_create_escalation_inherits_hitl_schema():
    schema = pydantic_to_hitl_schema(input_model=_Inputs)
    escalation = CreateEscalation(title="E", hitl_schema=schema)
    assert escalation.hitl_schema is schema


# ---------------------------------------------------------------------------
# _schema_key determinism
# ---------------------------------------------------------------------------


def test_schema_key_is_deterministic():
    schema = pydantic_to_hitl_schema(input_model=_Inputs, title="Test")
    key1 = _schema_key(schema)
    key2 = _schema_key(schema)
    assert key1 == key2


def test_different_schemas_produce_different_keys():
    schema_a = pydantic_to_hitl_schema(input_model=_Inputs, title="A")
    schema_b = pydantic_to_hitl_schema(input_model=_Inputs, title="B")
    assert _schema_key(schema_a) != _schema_key(schema_b)


def test_schema_key_is_valid_uuid_format():
    import uuid

    schema = pydantic_to_hitl_schema(input_model=_Inputs)
    key = _schema_key(schema)
    # Should not raise
    parsed = uuid.UUID(key)
    assert str(parsed) == key
