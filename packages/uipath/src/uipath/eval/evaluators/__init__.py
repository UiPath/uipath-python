"""UiPath evaluator implementations for agent performance evaluation."""

from typing import Any

# Platform-independent evaluators sourced from uipath-eval
from uipath_eval.evaluators import (
    EVALUATORS as _EVAL_EVALUATORS,
    BaseEvaluationCriteria,
    BaseEvaluator,
    BaseEvaluatorConfig,
    BaseEvaluatorJustification,
    BaseLegacyEvaluator,
    BinaryClassificationEvaluator,
    ContainsEvaluator,
    ExactMatchEvaluator,
    JsonSimilarityEvaluator,
    LegacyExactMatchEvaluator,
    LegacyJsonSimilarityEvaluator,
    MulticlassClassificationEvaluator,
    ToolCallArgsEvaluator,
    ToolCallCountEvaluator,
    ToolCallOrderEvaluator,
    ToolCallOutputEvaluator,
)

# Platform-dependent evaluators (LLM, langchain, uipath-platform) — stay in uipath
from .legacy_context_precision_evaluator import LegacyContextPrecisionEvaluator
from .legacy_csv_exact_match_evaluator import LegacyCSVExactMatchEvaluator
from .legacy_faithfulness_evaluator import LegacyFaithfulnessEvaluator
from .legacy_llm_as_judge_evaluator import LegacyLlmAsAJudgeEvaluator
from .legacy_trajectory_evaluator import LegacyTrajectoryEvaluator
from .llm_as_judge_evaluator import LLMJudgeJustification
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
from .output_evaluator import AggregationMethod

EVALUATORS: list[type[BaseEvaluator[Any, Any, Any]]] = [
    *_EVAL_EVALUATORS,
    LLMJudgeOutputEvaluator,
    LLMJudgeStrictJSONSimilarityOutputEvaluator,
    LLMJudgeTrajectoryEvaluator,
    LLMJudgeTrajectorySimulationEvaluator,
]
__all__ = [
    # Legacy evaluators
    "BaseLegacyEvaluator",
    "LegacyContextPrecisionEvaluator",
    "LegacyCSVExactMatchEvaluator",
    "LegacyExactMatchEvaluator",
    "LegacyFaithfulnessEvaluator",
    "LegacyLlmAsAJudgeEvaluator",
    "LegacyTrajectoryEvaluator",
    "LegacyJsonSimilarityEvaluator",
    # Current coded evaluators
    "BaseEvaluator",
    "BinaryClassificationEvaluator",
    "MulticlassClassificationEvaluator",
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
    "BaseEvaluatorJustification",
    "LLMJudgeJustification",
    "AggregationMethod",
]
