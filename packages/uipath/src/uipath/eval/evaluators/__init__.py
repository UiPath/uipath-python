"""UiPath evaluator implementations for agent performance evaluation."""

from typing import Any

# Platform-independent evaluators sourced from uipath-eval
from uipath_eval.evaluators import EVALUATORS as _EVAL_EVALUATORS
from uipath_eval.evaluators import (
    BaseEvaluationCriteria,
    BaseEvaluator,
    BaseEvaluatorConfig,
    BaseEvaluatorJustification,
    BinaryClassificationEvaluator,
    ContainsEvaluator,
    JsonSimilarityEvaluator,
    LegacyJsonSimilarityEvaluator,
    MulticlassClassificationEvaluator,
    ToolCallArgsEvaluator,
    ToolCallCountEvaluator,
    ToolCallOrderEvaluator,
    ToolCallOutputEvaluator,
)

# Platform-extended BaseLegacyEvaluator — extends uipath_eval's with line-by-line + attachments
from .base_legacy_evaluator import BaseLegacyEvaluator

# Platform-extended ExactMatchEvaluator — uses local OutputEvaluator with attachment support
from .exact_match_evaluator import ExactMatchEvaluator

# Platform-dependent evaluators (LLM, langchain, uipath-platform) — stay in uipath
from .legacy_context_precision_evaluator import LegacyContextPrecisionEvaluator
from .legacy_csv_exact_match_evaluator import LegacyCSVExactMatchEvaluator
from .legacy_exact_match_evaluator import LegacyExactMatchEvaluator
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
    # Replace uipath_eval.ExactMatchEvaluator with local version (has attachment support)
    *(
        e
        for e in _EVAL_EVALUATORS
        if e.get_evaluator_id() != ExactMatchEvaluator.get_evaluator_id()
    ),
    ExactMatchEvaluator,
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
