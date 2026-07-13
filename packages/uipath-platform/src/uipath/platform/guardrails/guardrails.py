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


class GuardrailType(str, Enum):
    """Guardrail type enumeration."""

    BUILT_IN_VALIDATOR = "builtInValidator"
    CUSTOM = "custom"
