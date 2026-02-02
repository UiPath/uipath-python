"""UiPath evaluator implementations for agent performance evaluation."""

from typing import Any

# Current coded evaluators
from .base_evaluator import BaseEvaluationCriteria, BaseEvaluator, BaseEvaluatorConfig
from .base_legacy_evaluator import BaseLegacyEvaluator

# Legacy evaluators
from .contains_evaluator import ContainsEvaluator
from .exact_match_evaluator import ExactMatchEvaluator
from .json_similarity_evaluator import JsonSimilarityEvaluator
from .legacy_context_precision_evaluator import LegacyContextPrecisionEvaluator
from .legacy_exact_match_evaluator import LegacyExactMatchEvaluator
from .legacy_faithfulness_evaluator import LegacyFaithfulnessEvaluator
from .legacy_json_similarity_evaluator import LegacyJsonSimilarityEvaluator
from .legacy_llm_as_judge_evaluator import LegacyLlmAsAJudgeEvaluator
from .legacy_trajectory_evaluator import LegacyTrajectoryEvaluator
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
    # Legacy evaluators
    "BaseLegacyEvaluator",
    "LegacyContextPrecisionEvaluator",
    "LegacyExactMatchEvaluator",
    "LegacyFaithfulnessEvaluator",
    "LegacyLlmAsAJudgeEvaluator",
    "LegacyTrajectoryEvaluator",
    "LegacyJsonSimilarityEvaluator",
    # Current coded evaluators
    "BaseEvaluator",
    "ContainsEvaluator",
    "ExactMatchEvaluator",
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
    "BaseEvaluationCriteria",
    "BaseEvaluatorConfig",
]
