from datetime import datetime
from enum import IntEnum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class LLMResponse(BaseModel):
    score: float
    justification: str


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


class EvaluationResult(BaseModel):
    """Result of a single evaluation."""

    evaluation_id: str
    evaluation_name: str
    evaluator_id: str
    evaluator_name: str
    score: float
    # mark this as optional, as it is populated inside the 'measure_execution_time' decorator
    evaluation_time: Optional[float] = None
    input: Dict[str, Any]
    expected_output: Dict[str, Any]
    actual_output: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    details: Optional[str] = None


class EvaluationSetResult(BaseModel):
    """Result of a complete evaluation set."""

    eval_set_id: str
    eval_set_name: str
    results: List[EvaluationResult]
    average_score: float


class ScoreType(IntEnum):
    BOOLEAN = 0
    NUMERICAL = 1
    ERROR = 2


class EvalItemResult(BaseModel):
    """Result of a single evaluation item."""

    evaluator_id: str
    result: EvaluationResult
