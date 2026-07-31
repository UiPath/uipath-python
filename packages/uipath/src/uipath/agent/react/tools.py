"""UiPath ReAct Agent Control Flow Tools."""

from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class FlowControlToolName(str, Enum):
    """Names of control flow tools."""

    END_EXECUTION = "end_execution"
    RAISE_ERROR = "raise_error"
    SET_CONVERSATIONAL_OUTPUT = "set_conversational_output"


@dataclass(frozen=True)
class FlowControlToolConfig:
    """Flow control tool configuration.

    Encapsulates the information needed to create a flow control tool
    """

    name: str
    description: str
    args_schema: type[BaseModel]


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


END_EXECUTION_TOOL = FlowControlToolConfig(
    name=FlowControlToolName.END_EXECUTION,
    description="Ends the execution of the agent",
    args_schema=EndExecutionToolSchemaModel,
)

RAISE_ERROR_TOOL = FlowControlToolConfig(
    name=FlowControlToolName.RAISE_ERROR,
    description="Raises an error and ends the execution of the agent",
    args_schema=RaiseErrorToolSchemaModel,
)


class SetConversationalOutputToolSchemaModel(BaseModel):
    """Placeholder args_schema for the `set_conversational_output` tool.

    Always overridden at construction time with the agent's stripped output
    schema (i.e. the user's `outputSchema` with `uipath__agent_response_messages`
    removed). Declared here so the tool entry has a well-typed default.
    """

    model_config = ConfigDict(extra="forbid")


SET_CONVERSATIONAL_OUTPUT_TOOL = FlowControlToolConfig(
    name=FlowControlToolName.SET_CONVERSATIONAL_OUTPUT,
    description=(
        "Sets the structured output fields for the current conversational "
        "turn. Called once per turn after the conversational response has been "
        "delivered, to populate fields as the agent's output."
    ),
    args_schema=SetConversationalOutputToolSchemaModel,
)
