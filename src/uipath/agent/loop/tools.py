"""LowCode Agent Tools."""

from pydantic import BaseModel, ConfigDict, Field

TOOL_FLOW_CONTROL_END_EXECUTION = "end_execution"
TOOL_FLOW_CONTROL_RAISE_ERROR = "raise_error"


class EndExecutionToolSchemaModel(BaseModel):
    """Arguments schema accepted by the `end_execution` control flow tool."""

    success: bool = Field(
        ...,
        description="Whether the execution was successful",
    )
    message: str | None = Field(
        None,
        description="The message to return to the user if the execution was successful",
    )
    error: str | None = Field(
        None,
        description="The error message to return to the user if the execution was unsuccessful",
    )

    model_config = ConfigDict(extra="forbid")


class RaiseErrorToolSchemaModel(BaseModel):
    """Arguments schema accepted by the `raise_error` control flow tool."""

    message: str = Field(
        ...,
        description="The error message to display to the user. This should be a brief one line message.",
    )
    details: str | None = Field(
        None,
        description=(
            "Optional additional details about the error. This can be a multiline text with more details. Only populate this if there are relevant details not already captured in the error message."
        ),
    )

    model_config = ConfigDict(extra="forbid")
