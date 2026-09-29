"""Models for the UiPath Business Rules service."""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class BusinessRuleStatus(str, Enum):
    """The overall outcome of running a business rule against one input."""

    SUCCESS = "Success"
    PARTIAL_SUCCESS = "PartialSuccess"
    ALL_FAILED = "AllFailed"


class RunMode(str, Enum):
    """Which kind of model ran, and so which service endpoint served the run."""

    DEPLOYED = "Deployed"


class DeployedRunContext(BaseModel):
    """A business rule deployed to Orchestrator."""

    rule_name: str = Field(description="The name of the deployed business rule.")
    version: Optional[str] = Field(
        default=None,
        description="The version to run; defaults to the active version.",
    )


class BusinessRuleError(BaseModel):
    """A code/message pair describing an input-level or decision-level error."""

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        extra="allow",
    )

    code: str = Field(default="", alias="code")
    message: str = Field(default="", alias="message")


class BusinessRuleDecision(BaseModel):
    """The result of evaluating a single decision."""

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        extra="allow",
    )

    decision_name: str = Field(default="", alias="decisionName")
    outputs: Optional[Dict[str, Any]] = Field(default=None, alias="outputs")
    error: Optional[BusinessRuleError] = Field(default=None, alias="error")


class BusinessRuleRunResult(BaseModel):
    """The outcome of running a business rule against one input."""

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
    )

    mode: RunMode = Field(description="Which kind of model ran.")
    status: BusinessRuleStatus
    decisions: List[BusinessRuleDecision] = Field(default_factory=list)
    errors: List[BusinessRuleError] = Field(
        default_factory=list,
        description="Errors that failed the input as a whole; non-empty means nothing was evaluated.",
    )
    top_level_error: Optional[str] = Field(
        default=None,
        description="The request-level error code (e.g. BATCH_TIMEOUT), if one was reported.",
    )
    business_rule_name: Optional[str] = Field(
        default=None, description="The deployed rule that ran."
    )
    version: Optional[str] = Field(
        default=None, description="The rule version that ran."
    )


class _WireResult(BaseModel):
    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    id: Optional[str] = None
    decisions: Optional[List[BusinessRuleDecision]] = None
    errors: Optional[List[BusinessRuleError]] = None


class _WireResponse(BaseModel):
    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="ignore"
    )

    business_rule_name: Optional[str] = Field(default=None, alias="businessRuleName")
    version: Optional[str] = None
    error: Optional[BusinessRuleError] = None
    results: Optional[List[_WireResult]] = None
