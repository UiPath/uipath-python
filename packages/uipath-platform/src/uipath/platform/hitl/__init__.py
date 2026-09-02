"""HITL form schema types and generator.

Provides Python-native representations of the HITL schema format and a utility
to generate schemas from Pydantic models.  The generated schema can be attached
to :class:`~uipath.platform.common.CreateTask` or
:class:`~uipath.platform.common.CreateEscalation` so the runtime creates a
QuickForm task with an inline schema instead of requiring a pre-deployed
Action App.

Example::

    from uipath.platform.hitl import HitlSchema, pydantic_to_hitl_schema
    from pydantic import BaseModel, Field

    class ReviewInputs(BaseModel):
        flagged_content: str = Field(title="Flagged Content")
        reason: str = Field(title="Reason")

    class ReviewOutputs(BaseModel):
        decision: str = Field(default="", title="Decision")
        notes: str = Field(default="", title="Notes")

    schema = pydantic_to_hitl_schema(
        input_model=ReviewInputs,
        output_model=ReviewOutputs,
        outcomes=["Approve", "Reject"],
        title="Content Review",
    )
"""

from .models import (
    HitlFieldDirection,
    HitlFieldType,
    HitlSchema,
    HitlSchemaField,
    HitlSchemaOutcome,
)
from .schema_gen import pydantic_to_hitl_schema

__all__ = [
    "HitlFieldDirection",
    "HitlFieldType",
    "HitlSchema",
    "HitlSchemaField",
    "HitlSchemaOutcome",
    "pydantic_to_hitl_schema",
]
