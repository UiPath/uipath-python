"""Models for the UiPath Business Rules service."""

import re
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

_HEX = re.compile(r"^[0-9a-f]+$")


class BusinessRuleStatus(str, Enum):
    """The overall outcome of running a business rule against one input."""

    SUCCESS = "Success"
    PARTIAL_SUCCESS = "PartialSuccess"
    ALL_FAILED = "AllFailed"


class RunMode(str, Enum):
    """Which kind of model ran, and so which service endpoint served the run."""

    DEPLOYED = "Deployed"
    DEBUG = "Debug"


class DebugRunContext(BaseModel):
    """Run an undeployed DMN from a Studio project instead of the deployed rule.

    With ``project_id`` the project is read as given. Without it, the service
    resolves the project from the running debug job's lineage, which needs
    ``job_key`` (defaults to ``UIPATH_JOB_KEY``) and ``organization_unit_id``.
    """

    project_id: Optional[str] = Field(
        default=None, description="The Studio project holding the DMN."
    )
    file_name: Optional[str] = Field(
        default=None,
        description="The .dmn file in the project; defaults to the first one.",
    )
    job_key: Optional[str] = Field(
        default=None,
        description="The debug job this run belongs to; defaults to UIPATH_JOB_KEY.",
    )
    organization_unit_id: Optional[int] = Field(
        default=None,
        description="The numeric id of the job's folder; required without project_id.",
    )


class TraceContext(BaseModel):
    """An existing trace to file the run's spans under.

    Optional on ``run()``: when omitted, the SDK takes the trace from
    ``UIPATH_TRACE_ID`` and the current span, as it does for every service.
    """

    trace_id: str = Field(
        description="The trace id: 32 hex characters, or a UUID with dashes."
    )
    parent_span_id: str = Field(
        description="The span the run's spans nest under: 16 hex characters."
    )

    @field_validator("trace_id")
    @classmethod
    def _normalize_trace_id(cls, value: str) -> str:
        normalized = value.replace("-", "").strip().lower()
        if len(normalized) != 32 or not _HEX.match(normalized):
            raise ValueError("trace_id must be 32 hex characters or a UUID")
        if normalized == "0" * 32:
            raise ValueError("trace_id must not be all zeros")
        return normalized

    @field_validator("parent_span_id")
    @classmethod
    def _normalize_parent_span_id(cls, value: str) -> str:
        normalized = value.strip().lower()
        if len(normalized) != 16 or not _HEX.match(normalized):
            raise ValueError("parent_span_id must be 16 hex characters")
        if normalized == "0" * 16:
            raise ValueError("parent_span_id must not be all zeros")
        return normalized

    def to_traceparent(self) -> str:
        """Return the W3C traceparent value for this context."""
        return f"00-{self.trace_id}-{self.parent_span_id}-01"


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
