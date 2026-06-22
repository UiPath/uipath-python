"""Python representation of the HITL form schema format.

Mirrors the TypeScript ``HitlSchema`` interface from ``@uipath/hitl-schema-types``
and is compatible with the QuickForm task endpoint
(``GenericTasks/CreateTask``, ``type=6``).
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class HitlFieldType(str, Enum):
    """Types supported by HITL form fields."""

    STRING = "string"
    NUMBER = "number"
    INTEGER = "integer"
    FLOAT = "float"
    DOUBLE = "double"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    FILE = "file"
    OBJECT = "object"
    ARRAY = "array"


class HitlFieldDirection(str, Enum):
    """Direction of a HITL form field.

    - ``INPUT``  — read-only display, pre-populated from task data.
    - ``OUTPUT`` — editable by the human reviewer, written to a variable on submit.
    - ``IN_OUT`` — both pre-populated and editable.
    """

    INPUT = "input"
    OUTPUT = "output"
    IN_OUT = "inOut"


class HitlSchemaField(BaseModel):
    """A single field in a HITL form schema."""

    id: str
    label: str | None = None
    type: HitlFieldType = HitlFieldType.STRING
    direction: HitlFieldDirection = HitlFieldDirection.INPUT
    required: bool | None = None


class HitlSchemaOutcome(BaseModel):
    """An outcome button in a HITL form schema (e.g. Approve / Reject)."""

    id: str
    label: str | None = None


class HitlSchema(BaseModel):
    """A dynamic HITL form schema generated from Python type annotations.

    Attach to :class:`~uipath.platform.common.CreateTask` or
    :class:`~uipath.platform.common.CreateEscalation` so the runtime creates a
    schema-driven QuickForm task instead of an action-app task.  No pre-deployed
    Action App is required when a schema is provided.
    """

    id: str | None = None
    title: str | None = None
    fields: list[HitlSchemaField] = Field(default_factory=list)
    outcomes: list[HitlSchemaOutcome] = Field(default_factory=list)

    def to_wire_format(self) -> dict[str, Any]:
        """Serialise to the dict expected by the QuickForm task API."""
        return self.model_dump(mode="json", exclude_none=True)
