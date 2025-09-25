"""Models for evaluation framework including execution data and evaluation results."""

import traceback
from enum import Enum, IntEnum
from typing import Annotated, Any, Dict, Literal, Optional, Union

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


class EvaluatorCategory(IntEnum):
    """Types of evaluators."""

    Deterministic = 0
    LlmAsAJudge = 1
    AgentScorer = 2
    Trajectory = 3

    @classmethod
    def from_int(cls, value: int) -> "EvaluatorCategory":
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
    def from_int(cls, value: int) -> "EvaluatorType":
        """Construct EvaluatorCategory from an int value."""
        if value in cls._value2member_map_:
            return cls(value)
        else:
            raise ValueError(f"{value} is not a valid EvaluatorType value")


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
