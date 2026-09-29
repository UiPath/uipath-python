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
    DEBUG = "Debug"


class DeployedRunContext(BaseModel):
    """A business rule deployed to Orchestrator."""

    rule_name: str = Field(description="The name of the deployed business rule.")
    version: Optional[str] = Field(
        default=None,
        description="The version to run; defaults to the active version.",
    )


class DebugRunContext(BaseModel):
    """An undeployed DMN read from a Studio project.

    Name the project with ``project_id``, or name the rule with ``rule_name`` and let
    the service resolve the project from the job's lineage. The second way also needs
    ``job_key`` (defaults to ``UIPATH_JOB_KEY``) and ``organization_unit_id``. When
    ``project_id`` is set, the project is used as given and neither is needed.
    """

    project_id: Optional[str] = Field(
        default=None, description="The Studio project holding the DMN."
    )
    rule_name: Optional[str] = Field(
        default=None,
        description="The business rule this run stands in for; the alternative to project_id.",
    )
    file_name: Optional[str] = Field(
        default=None,
        description="The .dmn file in the project; defaults to the first one.",
    )
    job_key: Optional[str] = Field(
        default=None,
        description="The job this run belongs to; defaults to UIPATH_JOB_KEY.",
    )
    organization_unit_id: Optional[int] = Field(
        default=None,
        description="The numeric id of the job's folder; required with rule_name alone.",
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
        default=None, description="The deployed rule that ran. Deployed mode only."
    )
    version: Optional[str] = Field(
        default=None, description="The rule version that ran. Deployed mode only."
    )
    project_id: Optional[str] = Field(
        default=None, description="The Studio project read. Debug mode only."
    )
    file_name: Optional[str] = Field(
        default=None,
        description="The .dmn file actually read, which may differ from the one asked for. Debug mode only.",
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
    project_id: Optional[str] = Field(default=None, alias="projectId")
    file_name: Optional[str] = Field(default=None, alias="fileName")
    error: Optional[BusinessRuleError] = None
    results: Optional[List[_WireResult]] = None
