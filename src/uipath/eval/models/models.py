"""Models for evaluation framework including execution data and evaluation results."""

import traceback
from dataclasses import dataclass
from enum import Enum, IntEnum
from typing import Annotated, Any, Dict, List, Literal, Optional, Union

from opentelemetry.sdk.trace import ReadableSpan
from pydantic import BaseModel, ConfigDict, Field


class AgentExecution(BaseModel):
    """Represents the execution data of an agent for evaluation purposes."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    agent_input: Optional[Dict[str, Any]]
    agent_output: Dict[str, Any]
    agent_trace: list[ReadableSpan]
    expected_agent_behavior: Optional[str] = None
    simulation_instructions: str = ""


class LLMResponse(BaseModel):
    """Response from an LLM evaluator."""

    score: float
    justification: str


class ScoreType(IntEnum):
    """Types of evaluation scores."""

    BOOLEAN = 0
    NUMERICAL = 1
    ERROR = 2


class BaseEvaluationResult(BaseModel):
    """Base class for evaluation results."""

    details: Optional[str | BaseModel] = None
    # this is marked as optional, as it is populated inside the 'measure_execution_time' decorator
    evaluation_time: Optional[float] = None


class BooleanEvaluationResult(BaseEvaluationResult):
    """Result of a boolean evaluation."""

    score: bool
    score_type: Literal[ScoreType.BOOLEAN] = ScoreType.BOOLEAN


class NumericEvaluationResult(BaseEvaluationResult):
    """Result of a numerical evaluation."""

    score: float
    score_type: Literal[ScoreType.NUMERICAL] = ScoreType.NUMERICAL


class ErrorEvaluationResult(BaseEvaluationResult):
    """Result of an error evaluation."""

    score: float = 0.0
    score_type: Literal[ScoreType.ERROR] = ScoreType.ERROR


EvaluationResult = Annotated[
    Union[BooleanEvaluationResult, NumericEvaluationResult, ErrorEvaluationResult],
    Field(discriminator="score_type"),
]


class EvalItemResult(BaseModel):
    """Result of a single evaluation item."""

    evaluator_id: str
    result: EvaluationResult


class LegacyEvaluatorCategory(IntEnum):
    """Types of evaluators."""

    Deterministic = 0
    LlmAsAJudge = 1
    AgentScorer = 2
    Trajectory = 3

    @classmethod
    def from_int(cls, value: int) -> "LegacyEvaluatorCategory":
        """Construct EvaluatorCategory from an int value."""
        if value in cls._value2member_map_:
            return cls(value)
        else:
            raise ValueError(f"{value} is not a valid EvaluatorCategory value")


class LegacyEvaluatorType(IntEnum):
    """Subtypes of evaluators."""

    Unknown = 0
    Equals = 1
    Contains = 2
    Regex = 3
    Factuality = 4
    Custom = 5
    JsonSimilarity = 6
    Trajectory = 7
    ContextPrecision = 8
    Faithfulness = 9

    @classmethod
    def from_int(cls, value: int) -> "LegacyEvaluatorType":
        """Construct EvaluatorCategory from an int value."""
        if value in cls._value2member_map_:
            return cls(value)
        else:
            raise ValueError(f"{value} is not a valid EvaluatorType value")


@dataclass
class TrajectoryEvaluationSpan:
    """Simplified span representation for trajectory evaluation.

    Contains span information needed for evaluating agent execution paths,
    excluding timestamps which are not useful for trajectory analysis.
    """

    name: str
    status: str
    attributes: Dict[str, Any]
    parent_name: Optional[str] = None
    events: Optional[List[Dict[str, Any]]] = None

    def __post_init__(self):
        """Initialize default values."""
        if self.events is None:
            self.events = []

    @classmethod
    def from_readable_span(
        cls, span: ReadableSpan, parent_spans: Optional[Dict[int, str]] = None
    ) -> "TrajectoryEvaluationSpan":
        """Convert a ReadableSpan to a TrajectoryEvaluationSpan.

        Args:
            span: The OpenTelemetry ReadableSpan to convert
            parent_spans: Optional mapping of span IDs to names for parent lookup

        Returns:
            TrajectoryEvaluationSpan with relevant data extracted
        """
        # Extract status
        status_map = {0: "unset", 1: "ok", 2: "error"}
        status = status_map.get(span.status.status_code.value, "unknown")

        # Extract attributes - keep all attributes for now
        attributes = {}
        if span.attributes:
            attributes = dict(span.attributes)

        # Get parent name if available
        parent_name = None
        if span.parent and parent_spans and span.parent.span_id in parent_spans:
            parent_name = parent_spans[span.parent.span_id]

        # Extract events (without timestamps)
        events = []
        if hasattr(span, "events") and span.events:
            for event in span.events:
                event_data = {
                    "name": event.name,
                    "attributes": dict(event.attributes) if event.attributes else {},
                }
                events.append(event_data)

        return cls(
            name=span.name,
            status=status,
            attributes=attributes,
            parent_name=parent_name,
            events=events,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "status": self.status,
            "parent_name": self.parent_name,
            "attributes": self.attributes,
            "events": self.events,
        }


class TrajectoryEvaluationTrace(BaseModel):
    """Container for a collection of trajectory evaluation spans."""

    spans: List[TrajectoryEvaluationSpan]

    @classmethod
    def from_readable_spans(
        cls, spans: List[ReadableSpan]
    ) -> "TrajectoryEvaluationTrace":
        """Convert a list of ReadableSpans to TrajectoryEvaluationTrace.

        Args:
            spans: List of OpenTelemetry ReadableSpans to convert

        Returns:
            TrajectoryEvaluationTrace with converted spans
        """
        # Create a mapping of span IDs to names for parent lookup
        span_id_to_name = {
            span.get_span_context().span_id: span.name  # pyright: ignore[reportOptionalMemberAccess]
            for span in spans
            if span.get_span_context() is not None
        }

        evaluation_spans = [
            TrajectoryEvaluationSpan.from_readable_span(span, span_id_to_name)
            for span in spans
        ]

        return cls(spans=evaluation_spans)

    class Config:
        """Pydantic configuration."""

        arbitrary_types_allowed = True


class EvaluatorType(str, Enum):
    """Evaluator type."""

    CONTAINS = "uipath-contains"
    EXACT_MATCH = "uipath-exact-match"
    JSON_SIMILARITY = "uipath-json-similarity"
    LLM_JUDGE_OUTPUT_SEMANTIC_SIMILARITY = "uipath-llm-judge-output-semantic-similarity"
    LLM_JUDGE_OUTPUT_STRICT_JSON_SIMILARITY = (
        "uipath-llm-judge-output-strict-json-similarity"
    )
    LLM_JUDGE_TRAJECTORY_SIMILARITY = "uipath-llm-judge-trajectory-similarity"
    LLM_JUDGE_TRAJECTORY_SIMULATION = "uipath-llm-judge-trajectory-simulation"
    LLM_JUDGE_TRAJECTORY = "uipath-llm-judge-trajectory"
    LLM_JUDGE_OUTPUT = "uipath-llm-judge-output"
    TOOL_CALL_ARGS = "uipath-tool-call-args"
    TOOL_CALL_COUNT = "uipath-tool-call-count"
    TOOL_CALL_ORDER = "uipath-tool-call-order"
    TOOL_CALL_OUTPUT = "uipath-tool-call-output"


class ToolCall(BaseModel):
    """Represents a tool call with its arguments."""

    name: str
    args: dict[str, Any]


class ToolOutput(BaseModel):
    """Represents a tool output with its output."""

    name: str
    output: str


class UiPathEvaluationErrorCategory(str, Enum):
    """Categories of evaluation errors."""

    SYSTEM = "System"
    USER = "User"
    UNKNOWN = "Unknown"


class UiPathEvaluationErrorContract(BaseModel):
    """Standard error contract used across the runtime."""

    code: str  # Human-readable code uniquely identifying this error type across the platform.
    # Format: <Component>.<PascalCaseErrorCode> (e.g. LangGraph.InvaliGraphReference)
    # Only use alphanumeric characters [A-Za-z0-9] and periods. No whitespace allowed.

    title: str  # Short, human-readable summary of the problem that should remain consistent
    # across occurrences.

    detail: (
        str  # Human-readable explanation specific to this occurrence of the problem.
    )
    # May include context, recommended actions, or technical details like call stacks
    # for technical users.

    category: UiPathEvaluationErrorCategory = UiPathEvaluationErrorCategory.UNKNOWN


class UiPathEvaluationError(Exception):
    """Base exception class for UiPath evaluation errors with structured error information."""

    def __init__(
        self,
        code: str,
        title: str,
        detail: str,
        category: UiPathEvaluationErrorCategory = UiPathEvaluationErrorCategory.UNKNOWN,
        prefix: str = "Python",
        include_traceback: bool = True,
    ):
        """Initialize the UiPathEvaluationError."""
        # Get the current traceback as a string
        if include_traceback:
            tb = traceback.format_exc()
            if (
                tb and tb.strip() != "NoneType: None"
            ):  # Ensure there's an actual traceback
                detail = f"{detail}\n\n{tb}"

        self.error_info = UiPathEvaluationErrorContract(
            code=f"{prefix}.{code}",
            title=title,
            detail=detail,
            category=category,
        )
        super().__init__(detail)

    @property
    def as_dict(self) -> Dict[str, Any]:
        """Get the error information as a dictionary."""
        return self.error_info.model_dump()
