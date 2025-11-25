"""Module defining the ActionSchema model for UiPath platform actions."""

from pydantic import BaseModel, ConfigDict, Field

class FieldDetails(BaseModel):
    """Model representing details of a field in an action schema."""

    name: str
    key: str

class ActionSchema(BaseModel):
    """Model representing the schema of an action in the UiPath platform."""

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
    )

    key: str
    in_outs: list[FieldDetails] | None = Field(default=None, alias="inOuts")
    inputs: list[FieldDetails] | None = None
    outputs: list[FieldDetails] | None = None
    outcomes: list[FieldDetails] | None = None
