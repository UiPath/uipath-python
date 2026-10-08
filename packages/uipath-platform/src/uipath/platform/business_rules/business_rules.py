"""Models for the UiPath Business Rules service."""

import re
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..common._span_utils import _SpanUtils

_HEX_DIGITS = re.compile(r"^[0-9a-f]+$")


class BusinessRuleStatus(str, Enum):
    """The overall outcome of running a business rule against one input."""

    SUCCESS = "Success"
    PARTIAL_SUCCESS = "PartialSuccess"
    ALL_FAILED = "AllFailed"


class BusinessRuleCaller(BaseModel):
    """Who is running the rule, kept in the deployed run's execution audit.

    Each field defaults to the current job's value from the environment. This
    describes the calling resource, not the rule: ``folder_key`` here is the
    caller's folder, which can differ from the folder the rule runs in.
    """

    resource_key: Optional[str] = Field(
        default=None,
        description="The calling resource's key; for a process, its release key. Defaults to UIPATH_PROCESS_UUID.",
    )
    run_key: Optional[str] = Field(
        default=None,
        description="The calling run, such as its job key. Defaults to UIPATH_JOB_KEY.",
    )
    folder_key: Optional[str] = Field(
        default=None,
        description="The folder the calling resource runs in. Defaults to UIPATH_FOLDER_KEY.",
    )
    is_debug_run: Optional[bool] = Field(
        default=None,
        description=(
            "Whether the calling run is a debug session, such as a process debugged "
            "in Studio Web; such a run may have no resource key to send. This is "
            "about the caller, not the rule: the deployed rule still runs. Defaults "
            "to whether the current job is a debug session."
        ),
    )


class BusinessRuleTraceContext(BaseModel):
    """An existing trace to file the run's spans under.

    Optional on ``run()``: when omitted, the SDK takes the trace from
    ``UIPATH_TRACE_ID`` and the current span, as it does for every service.
    """

    trace_id: str = Field(
        description="The trace id: 32 hex characters, or a UUID with dashes."
    )
    parent_span_id: str = Field(
        description=(
            "The span the run's spans nest under: 16 hex characters, or a UUID "
            "whose last 16 are used."
        )
    )

    @field_validator("trace_id")
    @classmethod
    def _normalize_trace_id(cls, value: str) -> str:
        try:
            trace_id = _SpanUtils.normalize_trace_id(value.strip())
        except ValueError:
            raise ValueError("trace_id must be 32 hex characters or a UUID") from None
        _require_nonzero_hex(trace_id, "trace_id")
        return trace_id

    @field_validator("parent_span_id")
    @classmethod
    def _normalize_parent_span_id(cls, value: str) -> str:
        try:
            span_id = _SpanUtils.normalize_span_id(value.strip())
        except ValueError:
            raise ValueError(
                "parent_span_id must be 16 hex characters or a UUID"
            ) from None
        _require_nonzero_hex(span_id, "parent_span_id")
        return span_id

    def to_traceparent(self) -> str:
        """Return the W3C traceparent value for this context."""
        return f"00-{self.trace_id}-{self.parent_span_id}-01"


def _require_nonzero_hex(trace_part: str, field_name: str) -> None:
    # _SpanUtils normalizes the form; the W3C traceparent also needs hex
    # digits, and an all-zero id is invalid there.
    if not _HEX_DIGITS.match(trace_part):
        raise ValueError(f"{field_name} must contain only hex characters")
    if not trace_part.strip("0"):
        raise ValueError(f"{field_name} must not be all zeros")


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
    """The outcome of running a business rule against one input.

    The shape is the same for deployed and debug runs.
    """

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
    )

    status: BusinessRuleStatus
    decisions: List[BusinessRuleDecision] = Field(default_factory=list)
    errors: List[BusinessRuleError] = Field(
        default_factory=list,
        description="Errors that failed the input as a whole; non-empty means nothing was evaluated.",
    )
    top_level_error: Optional[str] = Field(
        default=None,
        description="The request-level error code, if one was reported.",
    )
    business_rule_name: Optional[str] = Field(
        default=None, description="The deployed rule that ran, when reported."
    )
    version: Optional[str] = Field(
        default=None, description="The rule version that ran, when reported."
    )
    project_id: Optional[str] = Field(
        default=None,
        description="The Studio project the rule was read from, when it came from one.",
    )
    file_name: Optional[str] = Field(
        default=None,
        description="The rule file read from the project, when it came from one.",
    )


class _WireResult(BaseModel):
    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

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
    result: Optional[_WireResult] = None
