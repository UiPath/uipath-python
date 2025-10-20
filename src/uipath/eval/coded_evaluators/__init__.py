"""UiPath evaluator implementations for agent performance evaluation."""

from typing import Any

from .base_evaluator import BaseEvaluator
from .contains_evaluator import ContainsEvaluator
from .exact_match_evaluator import ExactMatchEvaluator
from .json_similarity_evaluator import JsonSimilarityEvaluator
from .llm_judge_output_evaluator import (
    BaseLLMOutputEvaluator,
    LLMJudgeOutputEvaluator,
    LLMJudgeStrictJSONSimilarityOutputEvaluator,
)
from .llm_judge_trajectory_evaluator import (
    BaseLLMTrajectoryEvaluator,
    LLMJudgeTrajectoryEvaluator,
    LLMJudgeTrajectorySimulationEvaluator,
)
from .tool_call_args_evaluator import ToolCallArgsEvaluator
from .tool_call_count_evaluator import ToolCallCountEvaluator
from .tool_call_order_evaluator import ToolCallOrderEvaluator
from .tool_call_output_evaluator import ToolCallOutputEvaluator

EVALUATORS: list[type[BaseEvaluator[Any, Any, Any]]] = [
    ExactMatchEvaluator,
    ContainsEvaluator,
    JsonSimilarityEvaluator,
    LLMJudgeOutputEvaluator,
    LLMJudgeStrictJSONSimilarityOutputEvaluator,
    LLMJudgeTrajectoryEvaluator,
    LLMJudgeTrajectorySimulationEvaluator,
    ToolCallOrderEvaluator,
    ToolCallArgsEvaluator,
    ToolCallCountEvaluator,
    ToolCallOutputEvaluator,
]

__all__ = [
    "BaseEvaluator",
    "LegacyExactMatchEvaluator",
    "ContainsEvaluator",
    "JsonSimilarityEvaluator",
    "BaseLLMOutputEvaluator",
    "LLMJudgeOutputEvaluator",
    "LLMJudgeStrictJSONSimilarityOutputEvaluator",
    "BaseLLMTrajectoryEvaluator",
    "LLMJudgeTrajectoryEvaluator",
    "LLMJudgeTrajectorySimulationEvaluator",
    "ToolCallOrderEvaluator",
    "ToolCallArgsEvaluator",
    "ToolCallCountEvaluator",
    "ToolCallOutputEvaluator",
]
