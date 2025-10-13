"""Models for evaluation framework including execution data and evaluation results."""

from dataclasses import dataclass
from enum import IntEnum
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

    details: Optional[str] = None
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


class EvaluatorCategory(IntEnum):
    """Types of evaluators."""

    Deterministic = 0
    LlmAsAJudge = 1
    AgentScorer = 2
    Trajectory = 3

    @classmethod
    def from_int(cls, value):
        """Construct EvaluatorCategory from an int value."""
        if value in cls._value2member_map_:
            return cls(value)
        else:
            raise ValueError(f"{value} is not a valid EvaluatorCategory value")


class EvaluatorType(IntEnum):
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
    def from_int(cls, value):
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
        span_id_to_name = {span.get_span_context().span_id: span.name for span in spans}

        evaluation_spans = [
            TrajectoryEvaluationSpan.from_readable_span(span, span_id_to_name)
            for span in spans
        ]

        return cls(spans=evaluation_spans)

    class Config:
        """Pydantic configuration."""

        arbitrary_types_allowed = True
