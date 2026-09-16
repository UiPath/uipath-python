"""Guardrails models for UiPath Platform."""

from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field
from uipath.core.guardrails import BaseGuardrail


class EnumListParameterValue(BaseModel):
    """Enum list parameter value."""

    parameter_type: Literal["enum-list"] = Field(alias="$parameterType")
    id: str
    value: list[str]

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class MapEnumParameterValue(BaseModel):
    """Map enum parameter value."""

    parameter_type: Literal["map-enum"] = Field(alias="$parameterType")
    id: str
    value: dict[str, float]

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class NumberParameterValue(BaseModel):
    """Number parameter value."""

    parameter_type: Literal["number"] = Field(alias="$parameterType")
    id: str
    value: float

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class EnumParameterValue(BaseModel):
    """Single-select enum parameter value."""

    parameter_type: Literal["enum"] = Field(alias="$parameterType")
    id: str
    value: str

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class TextParameterValue(BaseModel):
    """Free-text parameter value."""

    parameter_type: Literal["text"] = Field(alias="$parameterType")
    id: str
    value: str

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class TextListParameterValue(BaseModel):
    """List-of-text parameter value."""

    parameter_type: Literal["text-list"] = Field(alias="$parameterType")
    id: str
    value: list[str]

    model_config = ConfigDict(populate_by_name=True, extra="allow")


ValidatorParameter = Annotated[
    EnumListParameterValue
    | MapEnumParameterValue
    | NumberParameterValue
    | EnumParameterValue
    | TextParameterValue
    | TextListParameterValue,
    Field(discriminator="parameter_type"),
]


#: Sentinel ``validator_type`` for Bring Your Own Guardrail (BYOG) guardrails; the
#: connector-backed configuration is referenced by ``byo_validator_name`` instead.
BYO_VALIDATOR_TYPE = "byo"


class BuiltInValidatorGuardrail(BaseGuardrail):
    """Built-in validator guardrail model."""

    guardrail_type: Literal["builtInValidator"] = Field(alias="$guardrailType")
    validator_type: str = Field(alias="validatorType")
    validator_parameters: list[ValidatorParameter] = Field(
        default_factory=list, alias="validatorParameters"
    )
    byo_validator_name: str | None = Field(default=None, alias="byoValidatorName")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class GuardrailAttachment(BaseModel):
    """A reference to a file attached to the run that a guardrail may inspect.

    Passed to [`GuardrailsService.evaluate_guardrail`][uipath.platform.guardrails.GuardrailsService.evaluate_guardrail]
    so the guardrails backend can read the file's contents rather than only its metadata.

    Only the Orchestrator attachment id crosses the wire: helix resolves it through
    its own Orchestrator client (folder-scoped when the run's folder key is sent
    alongside), so Orchestrator's access control is what decides whether the file can
    be read — the runtime never resolves or forwards a signed URL itself.

    Attributes:
        id: The Orchestrator attachment id, as a string UUID. Used by the backend to
            resolve the file through Orchestrator, as an extraction cache key, and for
            trace correlation.
        file_name: Original file name, shown to a judge model so it can name the
            offending file.
        mime_type: Original mime type. The backend decides what it can inspect.
    """

    id: str
    file_name: str = Field(alias="fileName")
    mime_type: str = Field(alias="mimeType")

    model_config = ConfigDict(populate_by_name=True)


class GuardrailType(str, Enum):
    """Guardrail type enumeration."""

    BUILT_IN_VALIDATOR = "builtInValidator"
    CUSTOM = "custom"
