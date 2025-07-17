from datetime import datetime
from enum import IntEnum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class LLMResponse(BaseModel):
    similarity_score: float
    score_justification: str

class EvaluatorCategory(IntEnum):
    """Types of evaluators."""

    Deterministic = 0
    LlmAsAJudge = 1
    AgentScorer = 2
    Trajectory = 3


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


class EvaluationResult(BaseModel):
    """Result of a single evaluation."""

    evaluation_id: str
    evaluation_name: str
    evaluator_id: str
    evaluator_name: str
    score: float
    input: Dict[str, Any]
    expected_output: Dict[str, Any]
    actual_output: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    details: Optional[str] = None


class EvaluationSetResult(BaseModel):
    """Results of running an evaluation set."""

    eval_set_id: str
    eval_set_name: str
    results: List[EvaluationResult]
    average_score: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)
