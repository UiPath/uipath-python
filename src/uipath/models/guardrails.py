from enum import Enum
from typing import Annotated, Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator


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

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class FilterAction(BaseModel):
    """Filter action model."""

    action_type: Literal["filter"] = Field(alias="$actionType")
    fields: List[FieldReference]

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class SeverityLevel(str, Enum):
    """Severity level enumeration."""

    ERROR = "Error"
    INFO = "Info"
    WARNING = "Warning"


class LogAction(BaseModel):
    """Log action model."""

    action_type: Literal["log"] = Field(alias="$actionType")
    message: str = Field(..., alias="message")
    severity_level: SeverityLevel = Field(alias="severityLevel")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class EscalateActionApp(BaseModel):
    """Escalate action app model."""

    id: Optional[str] = None
    version: int
    name: str
    folder_id: Optional[str] = Field(None, alias="folderId")
    folder_name: str = Field(alias="folderName")
    app_process_key: Optional[str] = Field(None, alias="appProcessKey")
    runtime: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class AgentEscalationRecipientType(str, Enum):
    """Enum for escalation recipient types."""

    USER_ID = "UserId"
    GROUP_ID = "GroupId"
    USER_EMAIL = "UserEmail"


class AgentEscalationRecipient(BaseModel):
    """Recipient for escalation."""

    type: Union[AgentEscalationRecipientType, str] = Field(..., alias="type")
    value: str = Field(..., alias="value")
    display_name: Optional[str] = Field(default=None, alias="displayName")

    @field_validator("type", mode="before")
    @classmethod
    def normalize_type(cls, v: Any) -> str:
        """Normalize recipient type from int (1=UserId, 2=GroupId, 3=UserEmail) or string. Unknown integers are converted to string."""
        if isinstance(v, int):
            mapping = {
                1: AgentEscalationRecipientType.USER_ID,
                2: AgentEscalationRecipientType.GROUP_ID,
                3: AgentEscalationRecipientType.USER_EMAIL,
            }
            return mapping.get(v, str(v))
        return v

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class EscalateAction(BaseModel):
    """Escalate action model."""

    action_type: Literal["escalate"] = Field(alias="$actionType")
    app: EscalateActionApp
    recipient: AgentEscalationRecipient

    model_config = ConfigDict(populate_by_name=True, extra="allow")


GuardrailAction = Annotated[
    Union[BlockAction, FilterAction, LogAction, EscalateAction],
    Field(discriminator="action_type"),
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
    action: GuardrailAction
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

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class AgentGuardrailRule(BaseModel):
    """Guardrail validation rule."""

    rule_type: str = Field(..., alias="$ruleType")
    rule_type_alt: Optional[str] = Field(None, alias="ruleType")
    validator: str = Field(..., description="Validator type")
    parameters: List[AgentGuardrailRuleParameter] = Field(
        default_factory=list, description="Rule parameters"
    )

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class AgentGuardrailActionApp(BaseModel):
    """App configuration for guardrail actions."""

    name: str = Field(..., description="App name")
    version: str = Field(..., description="App version")
    folder_name: str = Field(..., alias="folderName", description="Folder name")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class AgentGuardrailActionRecipient(BaseModel):
    """Recipient for guardrail actions."""

    type: int = Field(..., description="Recipient type")
    value: str = Field(..., description="Recipient identifier")
    display_name: str = Field(..., alias="displayName", description="Display name")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class AgentGuardrailAction(BaseModel):
    """Action configuration for guardrails."""

    action_type: str = Field(..., alias="$actionType")
    action_type_alt: Optional[str] = Field(None, alias="actionType")
    app: AgentGuardrailActionApp = Field(..., description="App configuration")
    recipient: AgentGuardrailActionRecipient = Field(..., description="Recipient")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class AgentGuardrailSelector(BaseModel):
    """Selector for guardrail application scope."""

    scopes: List[str] = Field(..., description="Scopes where guardrail applies")
    match_names: List[str] = Field(
        ..., alias="matchNames", description="Names to match"
    )

    model_config = ConfigDict(populate_by_name=True, extra="allow")
