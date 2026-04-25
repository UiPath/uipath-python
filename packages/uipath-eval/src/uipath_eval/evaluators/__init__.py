"""UiPath evaluator implementations for agent performance evaluation.

Platform-dependent evaluators (LLMAsAJudge, LegacyContextPrecision,
LegacyFaithfulness, LegacyTrajectory) require uipath-platform and
remain in the uipath package.
"""

from typing import Any

from .base_evaluator import (
    BaseEvaluationCriteria,
    BaseEvaluator,
    BaseEvaluatorConfig,
    BaseEvaluatorJustification,
    GenericBaseEvaluator,
)
from .base_legacy_evaluator import BaseLegacyEvaluator
from .binary_classification_evaluator import BinaryClassificationEvaluator
from .contains_evaluator import ContainsEvaluator
from .exact_match_evaluator import ExactMatchEvaluator
from .json_similarity_evaluator import JsonSimilarityEvaluator
from .legacy_exact_match_evaluator import LegacyExactMatchEvaluator
from .legacy_json_similarity_evaluator import LegacyJsonSimilarityEvaluator
from .multiclass_classification_evaluator import MulticlassClassificationEvaluator
from .tool_call_args_evaluator import ToolCallArgsEvaluator
from .tool_call_count_evaluator import ToolCallCountEvaluator
from .tool_call_order_evaluator import ToolCallOrderEvaluator
from .tool_call_output_evaluator import ToolCallOutputEvaluator

EVALUATORS: list[type[BaseEvaluator[Any, Any, Any]]] = [
    ExactMatchEvaluator,
    ContainsEvaluator,
    BinaryClassificationEvaluator,
    MulticlassClassificationEvaluator,
    JsonSimilarityEvaluator,
    ToolCallOrderEvaluator,
    ToolCallArgsEvaluator,
    ToolCallCountEvaluator,
    ToolCallOutputEvaluator,
]

__all__ = [
    "EVALUATORS",
    "BaseEvaluationCriteria",
    "BaseEvaluator",
    "BaseEvaluatorConfig",
    "BaseEvaluatorJustification",
    "GenericBaseEvaluator",
    "BaseLegacyEvaluator",
    "BinaryClassificationEvaluator",
    "ContainsEvaluator",
    "ExactMatchEvaluator",
    "JsonSimilarityEvaluator",
    "LegacyExactMatchEvaluator",
    "LegacyJsonSimilarityEvaluator",
    "MulticlassClassificationEvaluator",
    "ToolCallArgsEvaluator",
    "ToolCallCountEvaluator",
    "ToolCallOrderEvaluator",
    "ToolCallOutputEvaluator",
]
