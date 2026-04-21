"""UiPath evaluator logic — standalone package.

Provides evaluators, models, and pure runtime utilities without
the full UiPath SDK. Intended for use in python-eval-workers.

For runtime integration (UiPathEvalRuntime, evaluate), use uipath.eval.
"""

from .evaluators import (
    EVALUATORS,
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
from .models import (
    AgentExecution,
    BooleanEvaluationResult,
    ErrorEvaluationResult,
    EvalItemResult,
    EvaluationResult,
    EvaluationResultDto,
    EvaluatorType,
    LegacyEvaluatorCategory,
    LegacyEvaluatorType,
    LLMResponse,
    NumericEvaluationResult,
    ScoreType,
    ToolCall,
    ToolOutput,
)

__all__ = [
    "EVALUATORS",
    # Base classes
    "BaseEvaluator",
    "BaseEvaluationCriteria",
    "BaseEvaluatorConfig",
    "BaseEvaluatorJustification",
    "BaseLegacyEvaluator",
    # Coded evaluators
    "BinaryClassificationEvaluator",
    "ContainsEvaluator",
    "ExactMatchEvaluator",
    "JsonSimilarityEvaluator",
    "MulticlassClassificationEvaluator",
    # Tool call evaluators
    "ToolCallArgsEvaluator",
    "ToolCallCountEvaluator",
    "ToolCallOrderEvaluator",
    "ToolCallOutputEvaluator",
    # Legacy evaluators (deterministic only — LLM/platform variants stay in uipath)
    "LegacyExactMatchEvaluator",
    "LegacyJsonSimilarityEvaluator",
    # Models
    "AgentExecution",
    "BooleanEvaluationResult",
    "ErrorEvaluationResult",
    "EvalItemResult",
    "EvaluationResult",
    "EvaluationResultDto",
    "EvaluatorType",
    "LegacyEvaluatorCategory",
    "LegacyEvaluatorType",
    "LLMResponse",
    "NumericEvaluationResult",
    "ScoreType",
    "ToolCall",
    "ToolOutput",
]
