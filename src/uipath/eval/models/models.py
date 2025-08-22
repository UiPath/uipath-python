"""Models for evaluation results and agent execution."""

from datetime import datetime, timezone
from enum import IntEnum
from typing import TYPE_CHECKING, Any, Optional, TypedDict

from pydantic import BaseModel, ConfigDict

from uipath.tracing import UiPathEvalSpan

if TYPE_CHECKING:
    from uipath.eval.evaluators import BaseEvaluator


class EvaluatorCategory(IntEnum):
    """Types of evaluators."""

    Custom = -1
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


class ScoreType(IntEnum):
    """Types of evaluation scores."""

    BOOLEAN = 0
    NUMERICAL = 1
    ERROR = 2


class EvaluationResult(BaseModel):
    """Result of a single evaluation."""

    score: float | bool
    score_type: ScoreType
    details: Optional[str] = None
    timestamp: datetime = datetime.now(timezone.utc)
    # this is marked as optional, as it is populated inside the 'measure_execution_time' decorator
    evaluation_time: Optional[float] = None


class AgentExecutionOutput(BaseModel):
    """Result of a single agent response."""

    actual_output: dict[str, Any]
    execution_time: float
    uipath_spans: list[UiPathEvalSpan]
    execution_logs: str


class LLMResponse(BaseModel):
    """Response from an LLM evaluator."""

    score: float
    justification: str
    error: bool = False

    def successful(self) -> bool:
        """Check if the LLM response was successful."""
        return self.error is False


class AgentInput(TypedDict):
    """Type hint for agent input dictionary."""

    pass


class ActualOutput(TypedDict):
    """Type hint for actual agent output dictionary."""

    pass


class ExpectedOutput(TypedDict):
    """Type hint for expected agent output dictionary."""

    pass


class AgentExecutionResult(BaseModel):
    """Result of agent execution before evaluation."""

    execution_time: float
    actual_output: dict[str, Any]
    execution_logs: str
    uipath_spans: list[UiPathEvalSpan]


class EvalItemResult(BaseModel):
    """Result of a single evaluation item."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    evaluator: "BaseEvaluator"
    result: EvaluationResult


class EvaluationPointResult(BaseModel):
    """Result of a single evaluation point."""

    agent_execution_time: float
    evaluators_results: list[EvalItemResult]
