"""Generate a :class:`HitlSchema` from Python type annotations.

The primary entry point is :func:`pydantic_to_hitl_schema`, which converts
Pydantic ``BaseModel`` classes into the :class:`HitlSchema` format consumed by
Action Center's QuickForm task endpoint.
"""

from __future__ import annotations

import inspect
import re
from types import UnionType
from typing import Any, Union, get_args, get_origin

from pydantic import BaseModel

from .models import (
    HitlFieldDirection,
    HitlFieldType,
    HitlSchema,
    HitlSchemaField,
    HitlSchemaOutcome,
)


def _annotation_to_hitl_type(annotation: Any) -> HitlFieldType:
    """Map a Python type annotation to the closest :class:`HitlFieldType`."""
    if annotation is None or annotation is inspect.Parameter.empty:
        return HitlFieldType.STRING

    origin = get_origin(annotation)
    args = get_args(annotation)

    # Handle Optional[T] / T | None (both typing.Union and PEP 604 UnionType)
    if origin is Union or isinstance(annotation, UnionType):
        non_none = [a for a in args if a is not type(None)]
        if non_none:
            return _annotation_to_hitl_type(non_none[0])
        return HitlFieldType.STRING

    if origin in (list, tuple):
        return HitlFieldType.ARRAY
    if origin is dict:
        return HitlFieldType.OBJECT

    if not inspect.isclass(annotation):
        return HitlFieldType.STRING

    # Check bool before int — bool is a subclass of int
    if issubclass(annotation, bool):
        return HitlFieldType.BOOLEAN
    if issubclass(annotation, int):
        return HitlFieldType.INTEGER
    if issubclass(annotation, float):
        return HitlFieldType.NUMBER
    if issubclass(annotation, str):
        return HitlFieldType.STRING
    if issubclass(annotation, (list, tuple)):
        return HitlFieldType.ARRAY
    if issubclass(annotation, dict):
        return HitlFieldType.OBJECT
    if issubclass(annotation, BaseModel):
        return HitlFieldType.OBJECT

    return HitlFieldType.STRING


def _label_from_name(name: str) -> str:
    """Produce a human-readable label from a snake_case or PascalCase name."""
    # PascalCase → insert space before each capital that follows a lowercase letter
    spaced = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name)
    # Underscores → spaces
    spaced = spaced.replace("_", " ")
    return spaced.title()


def pydantic_to_hitl_schema(
    *,
    input_model: type[BaseModel] | None = None,
    output_model: type[BaseModel] | None = None,
    outcomes: list[str] | None = None,
    title: str | None = None,
) -> HitlSchema:
    """Generate a :class:`HitlSchema` from Pydantic input and output models.

    Fields from *input_model* become ``direction="input"`` fields (read-only,
    pre-populated from task data).  Fields from *output_model* become
    ``direction="output"`` fields (editable by the human reviewer).

    The field ``id`` is taken from ``field_info.alias`` when one is set,
    otherwise from the Python field name.  Set an alias on a Pydantic field
    to control the id that Action Center uses (useful when the form contract
    requires PascalCase names but Python convention is snake_case).

    Args:
        input_model: Pydantic model for data shown to the reviewer.
        output_model: Pydantic model for data the reviewer fills in.
        outcomes: Outcome button labels.  Defaults to ``["Approve", "Reject"]``.
        title: Human-readable title for the form.

    Returns:
        A :class:`HitlSchema` ready to attach to
        :class:`~uipath.platform.common.CreateTask`.
    """
    if outcomes is None:
        outcomes = ["Approve", "Reject"]

    fields: list[HitlSchemaField] = []

    if input_model is not None:
        for name, field_info in input_model.model_fields.items():
            field_id = field_info.alias or name
            fields.append(
                HitlSchemaField(
                    id=str(field_id),
                    label=field_info.title or _label_from_name(str(field_id)),
                    type=_annotation_to_hitl_type(field_info.annotation),
                    direction=HitlFieldDirection.INPUT,
                    required=True if field_info.is_required() else None,
                )
            )

    if output_model is not None:
        for name, field_info in output_model.model_fields.items():
            field_id = field_info.alias or name
            fields.append(
                HitlSchemaField(
                    id=str(field_id),
                    label=field_info.title or _label_from_name(str(field_id)),
                    type=_annotation_to_hitl_type(field_info.annotation),
                    direction=HitlFieldDirection.OUTPUT,
                    required=None,
                )
            )

    return HitlSchema(
        title=title,
        fields=fields,
        outcomes=[
            HitlSchemaOutcome(id=outcome.lower(), label=outcome)
            for outcome in outcomes
        ],
    )
