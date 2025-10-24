from enum import Enum
from typing import Annotated, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


class FieldSource(str, Enum):
    """Field source enumeration."""

    INPUT = "input"
    OUTPUT = "output"


class ApplyTo(str, Enum):
    """Apply to enumeration."""

    INPUT = "input"
    INPUT_AND_OUTPUT = "inputAndOutput"
    OUTPUT = "output"


class FieldReference(BaseModel):
    """Field reference model."""

    path: str
    source: FieldSource

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class SelectorType(str, Enum):
    """Selector type enumeration."""

    ALL = "all"
    SPECIFIC = "specific"


class AllFieldsSelector(BaseModel):
    """All fields selector."""

    selector_type: Literal["all"] = Field(alias="$selectorType")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class SpecificFieldsSelector(BaseModel):
    """Specific fields selector."""

    selector_type: Literal["specific"] = Field(alias="$selectorType")
    fields: List[FieldReference]

    model_config = ConfigDict(populate_by_name=True, extra="allow")


FieldSelector = Annotated[
    Union[AllFieldsSelector, SpecificFieldsSelector],
    Field(discriminator="selector_type"),
]


class RuleType(str, Enum):
    """Rule type enumeration."""

    BOOLEAN = "boolean"
    NUMBER = "number"
    UNIVERSAL = "always"
    WORD = "word"


class WordOperator(str, Enum):
    """Word operator enumeration."""

    CONTAINS = "contains"
    DOES_NOT_CONTAIN = "doesNotContain"
    DOES_NOT_END_WITH = "doesNotEndWith"
    DOES_NOT_EQUAL = "doesNotEqual"
    DOES_NOT_START_WITH = "doesNotStartWith"
    ENDS_WITH = "endsWith"
    EQUALS = "equals"
    IS_EMPTY = "isEmpty"
    IS_NOT_EMPTY = "isNotEmpty"
    STARTS_WITH = "startsWith"


class WordRule(BaseModel):
    """Word rule model."""

    rule_type: Literal["word"] = Field(alias="$ruleType")
    field_selector: FieldSelector = Field(alias="fieldSelector")
    operator: WordOperator
    value: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class UniversalRule(BaseModel):
    """Universal rule model."""

    rule_type: Literal["always"] = Field(alias="$ruleType")
    apply_to: ApplyTo = Field(alias="applyTo")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class NumberOperator(str, Enum):
    """Number operator enumeration."""

    DOES_NOT_EQUAL = "doesNotEqual"
    EQUALS = "equals"
    GREATER_THAN = "greaterThan"
    GREATER_THAN_OR_EQUAL = "greaterThanOrEqual"
    LESS_THAN = "lessThan"
    LESS_THAN_OR_EQUAL = "lessThanOrEqual"


class NumberRule(BaseModel):
    """Number rule model."""

    rule_type: Literal["number"] = Field(alias="$ruleType")
    field_selector: FieldSelector = Field(alias="fieldSelector")
    operator: NumberOperator
    value: float

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class BooleanOperator(str, Enum):
    """Boolean operator enumeration."""

    EQUALS = "equals"


class BooleanRule(BaseModel):
    """Boolean rule model."""

    rule_type: Literal["boolean"] = Field(alias="$ruleType")
    field_selector: FieldSelector = Field(alias="fieldSelector")
    operator: BooleanOperator
    value: bool

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class EnumListParameterValue(BaseModel):
    """Enum list parameter value."""

    parameter_type: Literal["enum-list"] = Field(alias="$parameterType")
    id: str
    value: List[str]

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class MapEnumParameterValue(BaseModel):
    """Map enum parameter value."""

    parameter_type: Literal["map-enum"] = Field(alias="$parameterType")
    id: str
    value: Dict[str, float]

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class NumberParameterValue(BaseModel):
    """Number parameter value."""

    parameter_type: Literal["number"] = Field(alias="$parameterType")
    id: str
    value: float

    model_config = ConfigDict(populate_by_name=True, extra="allow")


ValidatorParameter = Annotated[
    Union[EnumListParameterValue, MapEnumParameterValue, NumberParameterValue],
    Field(discriminator="parameter_type"),
]


Rule = Annotated[
    Union[WordRule, NumberRule, BooleanRule, UniversalRule],
    Field(discriminator="rule_type"),
]


class GuardrailScope(str, Enum):
    """Guardrail scope enumeration."""

    AGENT = "Agent"
    LLM = "Llm"
    TOOL = "Tool"


class GuardrailSelector(BaseModel):
    """Guardrail selector model."""

    scopes: List[GuardrailScope] = Field(default=[GuardrailScope.TOOL])
    match_names: Optional[List[str]] = Field(None, alias="matchNames")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class BaseGuardrail(BaseModel):
    """Base guardrail model."""

    id: str
    name: str
    description: Optional[str] = None
    enabled_for_evals: bool = Field(True, alias="enabledForEvals")
    selector: GuardrailSelector

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class CustomGuardrail(BaseGuardrail):
    """Custom guardrail model."""

    guardrail_type: Literal["custom"] = Field(alias="$guardrailType")
    rules: List[Rule]

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class BuiltInValidatorGuardrail(BaseGuardrail):
    """Built-in validator guardrail model."""

    guardrail_type: Literal["builtInValidator"] = Field(alias="$guardrailType")
    validator_type: str = Field(alias="validatorType")
    validator_parameters: List[ValidatorParameter] = Field(
        default_factory=list, alias="validatorParameters"
    )

    model_config = ConfigDict(populate_by_name=True, extra="allow")


Guardrail = Annotated[
    Union[CustomGuardrail, BuiltInValidatorGuardrail],
    Field(discriminator="guardrail_type"),
]


class GuardrailType(str, Enum):
    """Guardrail type enumeration."""

    BUILT_IN_VALIDATOR = "builtInValidator"
    CUSTOM = "custom"
