"""Models for evaluation framework including execution data and evaluation results."""

from enum import IntEnum
from typing import Annotated, Any, Dict, Literal, Optional, Union

from opentelemetry.sdk.trace import ReadableSpan
from pydantic import BaseModel, ConfigDict, Field


class AgentExecution(BaseModel):
    """Represents the execution data of an agent for evaluation purposes."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    agent_input: Optional[Dict[str, Any]]
    agent_output: Dict[str, Any]
    agent_trace: list[ReadableSpan]


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
