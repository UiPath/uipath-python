from enum import Enum
from typing import TYPE_CHECKING, Annotated, Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Discriminator, Field, Tag


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

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class SelectorType(str, Enum):
    """Selector type enumeration."""

    ALL = "all"
    SPECIFIC = "specific"


class AllFieldsSelector(BaseModel):
    """All fields selector."""

    selector_type: Literal["all"] = Field(alias="$selectorType")

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class SpecificFieldsSelector(BaseModel):
    """Specific fields selector."""

    selector_type: Literal["specific"] = Field(alias="$selectorType")
    fields: List[FieldReference]

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


def field_selector_discriminator(data: Any) -> str:
    """Discriminator for field selectors."""
    if isinstance(data, dict):
        selector_type = data.get("$selectorType")
        if selector_type == "all":
            return "AllFieldsSelector"
        elif selector_type == "specific":
            return "SpecificFieldsSelector"
    raise ValueError("Invalid field selector discriminator values")


FieldSelector = Annotated[
    Union[
        Annotated[AllFieldsSelector, Tag("AllFieldsSelector")],
        Annotated[SpecificFieldsSelector, Tag("SpecificFieldsSelector")],
    ],
    Field(discriminator=Discriminator(field_selector_discriminator)),
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

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class UniversalRule(BaseModel):
    """Universal rule model."""

    rule_type: Literal["always"] = Field(alias="$ruleType")
    apply_to: ApplyTo = Field(alias="applyTo")

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


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

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class BooleanOperator(str, Enum):
    """Boolean operator enumeration."""

    EQUALS = "equals"


class BooleanRule(BaseModel):
    """Boolean rule model."""

    rule_type: Literal["boolean"] = Field(alias="$ruleType")
    field_selector: FieldSelector = Field(alias="fieldSelector")
    operator: BooleanOperator
    value: bool

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class EnumListParameterValue(BaseModel):
    """Enum list parameter value."""

    parameter_type: Literal["enum-list"] = Field(alias="$parameterType")
    id: str
    value: List[str]

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class MapEnumParameterValue(BaseModel):
    """Map enum parameter value."""

    parameter_type: Literal["map-enum"] = Field(alias="$parameterType")
    id: str
    value: Dict[str, float]

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class NumberParameterValue(BaseModel):
    """Number parameter value."""

    parameter_type: Literal["number"] = Field(alias="$parameterType")
    id: str
    value: float

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


def validator_parameter_discriminator(data: Any) -> str:
    """Discriminator for validator parameters."""
    if isinstance(data, dict):
        param_type = data.get("$parameterType")
        if param_type == "enum-list":
            return "EnumListParameterValue"
        elif param_type == "map-enum":
            return "MapEnumParameterValue"
        elif param_type == "number":
            return "NumberParameterValue"
    raise ValueError("Invalid validator parameter discriminator values")


ValidatorParameter = Annotated[
    Union[
        Annotated[EnumListParameterValue, Tag("EnumListParameterValue")],
        Annotated[MapEnumParameterValue, Tag("MapEnumParameterValue")],
        Annotated[NumberParameterValue, Tag("NumberParameterValue")],
    ],
    Field(discriminator=Discriminator(validator_parameter_discriminator)),
]


def rule_discriminator(data: Any) -> str:
    """Discriminator for rules."""
    if isinstance(data, dict):
        rule_type = data.get("$ruleType")
        if rule_type == "word":
            return "WordRule"
        elif rule_type == "number":
            return "NumberRule"
        elif rule_type == "boolean":
            return "BooleanRule"
        elif rule_type == "always":
            return "UniversalRule"
    raise ValueError("Invalid rule discriminator values")


Rule = Annotated[
    Union[
        Annotated[WordRule, Tag("WordRule")],
        Annotated[NumberRule, Tag("NumberRule")],
        Annotated[BooleanRule, Tag("BooleanRule")],
        Annotated[UniversalRule, Tag("UniversalRule")],
    ],
    Field(discriminator=Discriminator(rule_discriminator)),
]


class ActionType(str, Enum):
    """Action type enumeration."""

    BLOCK = "block"
    ESCALATE = "escalate"
    FILTER = "filter"
    LOG = "log"


class BlockAction(BaseModel):
    """Block action model."""

    action_type: Literal["block"] = Field(alias="$actionType")
    reason: str

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class FilterAction(BaseModel):
    """Filter action model."""

    action_type: Literal["filter"] = Field(alias="$actionType")
    fields: List[FieldReference]

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class SeverityLevel(str, Enum):
    """Severity level enumeration."""

    ERROR = "Error"
    INFO = "Info"
    WARNING = "Warning"


class LogAction(BaseModel):
    """Log action model."""

    action_type: Literal["log"] = Field(alias="$actionType")
    severity_level: SeverityLevel = Field(alias="severityLevel")

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class EscalateActionApp(BaseModel):
    """Escalate action app model."""

    id: str
    version: str
    name: str
    folder_id: Optional[str] = Field(None, alias="folderId")
    folder_name: Optional[str] = Field(None, alias="folderName")
    app_process_key: Optional[str] = Field(None, alias="appProcessKey")
    runtime: Optional[str] = None

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class AgentEscalationRecipient(BaseModel):
    """Recipient for escalation."""

    type: int = Field(..., alias="type")
    value: str = Field(..., alias="value")
    display_name: Optional[str] = Field(default=None, alias="displayName")
    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class EscalateAction(BaseModel):
    """Escalate action model."""

    action_type: Literal["escalate"] = Field(alias="$actionType")
    app: EscalateActionApp
    recipient: AgentEscalationRecipient

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


def guardrail_action_discriminator(data: Any) -> str:
    """Discriminator for guardrail actions."""
    if isinstance(data, dict):
        action_type = data.get("$actionType")
        if action_type == "block":
            return "BlockAction"
        elif action_type == "filter":
            return "FilterAction"
        elif action_type == "log":
            return "LogAction"
        elif action_type == "escalate":
            return "EscalateAction"
    raise ValueError("Invalid guardrail action discriminator values")


GuardrailAction = Annotated[
    Union[
        Annotated[BlockAction, Tag("BlockAction")],
        Annotated[FilterAction, Tag("FilterAction")],
        Annotated[LogAction, Tag("LogAction")],
        Annotated[EscalateAction, Tag("EscalateAction")],
    ],
    Field(discriminator=Discriminator(guardrail_action_discriminator)),
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

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class BaseGuardrail(BaseModel):
    """Base guardrail model."""

    id: str
    name: str
    description: Optional[str] = None
    action: GuardrailAction
    enabled_for_evals: bool = Field(True, alias="enabledForEvals")
    selector: GuardrailSelector

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class CustomGuardrail(BaseGuardrail):
    """Custom guardrail model."""

    guardrail_type: Literal["custom"] = Field(alias="$guardrailType")
    rules: List[Rule]

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class BuiltInValidatorGuardrail(BaseGuardrail):
    """Built-in validator guardrail model."""

    guardrail_type: Literal["builtInValidator"] = Field(alias="$guardrailType")
    validator_type: str = Field(alias="validatorType")
    validator_parameters: List[ValidatorParameter] = Field(
        default_factory=list, alias="validatorParameters"
    )

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


def guardrail_discriminator(data: Any) -> str:
    """Discriminator for guardrails."""
    if isinstance(data, dict):
        guardrail_type = data.get("$guardrailType")
        if guardrail_type == "custom":
            return "CustomGuardrail"
        elif guardrail_type == "builtInValidator":
            return "BuiltInValidatorGuardrail"
    raise ValueError("Invalid guardrail discriminator values")


Guardrail = Annotated[
    Union[
        Annotated[CustomGuardrail, Tag("CustomGuardrail")],
        Annotated[BuiltInValidatorGuardrail, Tag("BuiltInValidatorGuardrail")],
    ],
    Field(discriminator=Discriminator(guardrail_discriminator)),
]


class GuardrailType(str, Enum):
    """Guardrail type enumeration."""

    BUILT_IN_VALIDATOR = "builtInValidator"
    CUSTOM = "custom"


# Helper functions for type checking
def is_boolean_rule(rule: Rule) -> bool:
    """Check if rule is a BooleanRule."""
    return hasattr(rule, "rule_type") and rule.rule_type == RuleType.BOOLEAN


def is_number_rule(rule: Rule) -> bool:
    """Check if rule is a NumberRule."""
    return hasattr(rule, "rule_type") and rule.rule_type == RuleType.NUMBER


def is_universal_rule(rule: Rule) -> bool:
    """Check if rule is a UniversalRule."""
    return hasattr(rule, "rule_type") and rule.rule_type == RuleType.UNIVERSAL


def is_word_rule(rule: Rule) -> bool:
    """Check if rule is a WordRule."""
    return hasattr(rule, "rule_type") and rule.rule_type == RuleType.WORD


def is_custom_guardrail(guardrail: Guardrail) -> bool:
    """Check if guardrail is a CustomGuardrail."""
    return (
        hasattr(guardrail, "guardrail_type")
        and guardrail.guardrail_type == GuardrailType.CUSTOM
    )


def is_built_in_validator_guardrail(guardrail: Guardrail) -> bool:
    """Check if guardrail is a BuiltInValidatorGuardrail."""
    return (
        hasattr(guardrail, "guardrail_type")
        and guardrail.guardrail_type == GuardrailType.BUILT_IN_VALIDATOR
    )


def is_valid_action_type(value: Any) -> bool:
    """Check if value is a valid ActionType."""
    return isinstance(value, str) and value.lower() in [
        at.value.lower() for at in ActionType
    ]


def is_valid_severity_level(value: Any) -> bool:
    """Check if value is a valid SeverityLevel."""
    return isinstance(value, str) and value in [sl.value for sl in SeverityLevel]


# Guardrail Models
class AgentGuardrailRuleParameter(BaseModel):
    """Parameter for guardrail rules."""

    parameter_type: str = Field(..., alias="$parameterType")
    parameter_type_alt: Optional[str] = Field(None, alias="parameterType")
    value: Any = Field(..., description="Parameter value")
    id: str = Field(..., description="Parameter identifier")

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class AgentGuardrailRule(BaseModel):
    """Guardrail validation rule."""

    rule_type: str = Field(..., alias="$ruleType")
    rule_type_alt: Optional[str] = Field(None, alias="ruleType")
    validator: str = Field(..., description="Validator type")
    parameters: List[AgentGuardrailRuleParameter] = Field(
        default_factory=list, description="Rule parameters"
    )

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class AgentGuardrailActionApp(BaseModel):
    """App configuration for guardrail actions."""

    name: str = Field(..., description="App name")
    version: str = Field(..., description="App version")
    folder_name: str = Field(..., alias="folderName", description="Folder name")

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class AgentGuardrailActionRecipient(BaseModel):
    """Recipient for guardrail actions."""

    type: int = Field(..., description="Recipient type")
    value: str = Field(..., description="Recipient identifier")
    display_name: str = Field(..., alias="displayName", description="Display name")

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class AgentGuardrailAction(BaseModel):
    """Action configuration for guardrails."""

    action_type: str = Field(..., alias="$actionType")
    action_type_alt: Optional[str] = Field(None, alias="actionType")
    app: AgentGuardrailActionApp = Field(..., description="App configuration")
    recipient: AgentGuardrailActionRecipient = Field(..., description="Recipient")

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class AgentGuardrailSelector(BaseModel):
    """Selector for guardrail application scope."""

    scopes: List[str] = Field(..., description="Scopes where guardrail applies")
    match_names: List[str] = Field(
        ..., alias="matchNames", description="Names to match"
    )

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )
