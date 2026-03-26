"""Guardrails models for UiPath Platform."""

from enum import Enum
from typing import Annotated, Any, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _decapitalize_first_letter(s: str) -> str:
    """Convert first letter to lowercase (e.g., 'SimpleText' -> 'simpleText')."""
    if not s or len(s) == 0:
        return s
    if len(s) == 1:
        return s.lower()
    return s[0].lower() + s[1:]


class GuardrailValidationResultType(str, Enum):
    """Guardrail validation result type enumeration."""

    PASSED = "passed"
    VALIDATION_FAILED = "validation_failed"
    ENTITLEMENTS_MISSING = "entitlements_missing"
    FEATURE_DISABLED = "feature_disabled"


class GuardrailValidationResult(BaseModel):
    """Result returned from validating input with a given guardrail.

    Attributes:
        result: The validation result type.
        reason: Textual explanation describing why the validation passed or failed.
    """

    model_config = ConfigDict(populate_by_name=True)

    result: GuardrailValidationResultType = Field(
        alias="result", description="Validation result."
    )
    reason: str = Field(
        alias="reason", description="Explanation for the validation result."
    )


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

    @field_validator("source", mode="before")
    @classmethod
    def normalize_type(cls, v: Any) -> Any:
        """Normalize type by decapitalizing first letter."""
        return _decapitalize_first_letter(v) if isinstance(v, str) else v


class SelectorType(str, Enum):
    """Selector type enumeration."""

    ALL = "all"
    SPECIFIC = "specific"


class AllFieldsSelector(BaseModel):
    """All fields selector."""

    selector_type: Literal["all"] = Field(alias="$selectorType")
    sources: list[FieldSource]

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    @field_validator("sources", mode="before")
    @classmethod
    def normalize_sources(cls, v: Any) -> Any:
        """Normalize sources by decapitalizing first letter of each item."""
        if isinstance(v, list):
            return [
                _decapitalize_first_letter(item) if isinstance(item, str) else item
                for item in v
            ]
        return v


class SpecificFieldsSelector(BaseModel):
    """Specific fields selector."""

    selector_type: Literal["specific"] = Field(alias="$selectorType")
    fields: list[FieldReference]

    model_config = ConfigDict(populate_by_name=True, extra="allow")


FieldSelector = Annotated[
    AllFieldsSelector | SpecificFieldsSelector,
    Field(discriminator="selector_type"),
]


class RuleType(str, Enum):
    """Rule type enumeration."""

    BOOLEAN = "boolean"
    NUMBER = "number"
    UNIVERSAL = "always"
    WORD = "word"


class WordRule(BaseModel):
    """Word rule model."""

    rule_type: Literal["word"] = Field(alias="$ruleType")
    field_selector: FieldSelector = Field(alias="fieldSelector")
    rule_description: str | None = Field(
        default=None,
        exclude=True,
        description="Human-friendly description of the rule condition.",
    )
    detects_violation: Callable[[str], bool] = Field(
        exclude=True,
        description="Function that returns True if the string violates the rule (validation should fail).",
    )

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class UniversalRule(BaseModel):
    """Universal rule model."""

    rule_type: Literal["always"] = Field(alias="$ruleType")
    apply_to: ApplyTo = Field(alias="applyTo")
    rule_description: str | None = Field(
        default=None,
        exclude=True,
        description="Human-friendly description of the rule condition.",
    )

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    @field_validator("apply_to", mode="before")
    @classmethod
    def normalize_type(cls, v: Any) -> Any:
        """Normalize type by decapitalizing first letter."""
        return _decapitalize_first_letter(v) if isinstance(v, str) else v


class NumberRule(BaseModel):
    """Number rule model."""

    rule_type: Literal["number"] = Field(alias="$ruleType")
    field_selector: FieldSelector = Field(alias="fieldSelector")
    rule_description: str | None = Field(
        default=None,
        exclude=True,
        description="Human-friendly description of the rule condition.",
    )
    detects_violation: Callable[[float], bool] = Field(
        exclude=True,
        description="Function that returns True if the number violates the rule (validation should fail).",
    )

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class BooleanRule(BaseModel):
    """Boolean rule model."""

    rule_type: Literal["boolean"] = Field(alias="$ruleType")
    field_selector: FieldSelector = Field(alias="fieldSelector")
    rule_description: str | None = Field(
        default=None,
        exclude=True,
        description="Human-friendly description of the rule condition.",
    )
    detects_violation: Callable[[bool], bool] = Field(
        exclude=True,
        description="Function that returns True if the boolean violates the rule (validation should fail).",
    )

    model_config = ConfigDict(populate_by_name=True, extra="allow")


Rule = Annotated[
    WordRule | NumberRule | BooleanRule | UniversalRule,
    Field(discriminator="rule_type"),
]


class GuardrailScope(str, Enum):
    """Guardrail scope enumeration."""

    AGENT = "Agent"
    LLM = "Llm"
    TOOL = "Tool"


class GuardrailSelector(BaseModel):
    """Guardrail selector model."""

    scopes: list[GuardrailScope] = Field(default=[GuardrailScope.TOOL])
    match_names: list[str] | None = Field(None, alias="matchNames")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class BaseGuardrail(BaseModel):
    """Base guardrail model."""

    id: str
    name: str
    description: str | None = None
    enabled_for_evals: bool = Field(True, alias="enabledForEvals")
    selector: GuardrailSelector

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class DeterministicGuardrail(BaseGuardrail):
    """Deterministic guardrail model."""

    guardrail_type: Literal["custom"] = Field(alias="$guardrailType")
    rules: list[Rule]

    model_config = ConfigDict(populate_by_name=True, extra="allow")
