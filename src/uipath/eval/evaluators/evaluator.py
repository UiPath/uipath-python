"""Evaluator definitions and discriminators for legacy and coded evaluators."""

from typing import Annotated, Any, Union

from pydantic import ConfigDict, Discriminator, Field, Tag

from uipath.eval.evaluators import (
    BaseLegacyEvaluator,
    ContainsEvaluator,
    ExactMatchEvaluator,
    JsonSimilarityEvaluator,
    LegacyExactMatchEvaluator,
    LegacyJsonSimilarityEvaluator,
    LegacyLlmAsAJudgeEvaluator,
    LegacyTrajectoryEvaluator,
    LLMJudgeOutputEvaluator,
    LLMJudgeStrictJSONSimilarityOutputEvaluator,
    LLMJudgeTrajectoryEvaluator,
    LLMJudgeTrajectorySimulationEvaluator,
    ToolCallArgsEvaluator,
    ToolCallCountEvaluator,
    ToolCallOrderEvaluator,
    ToolCallOutputEvaluator,
)
from uipath.eval.evaluators.base_evaluator import BaseEvaluator, BaseEvaluatorConfig
from uipath.eval.models import (
    EvaluatorType,
    LegacyEvaluatorCategory,
    LegacyEvaluatorType,
)


class UnknownLegacyEvaluator(BaseLegacyEvaluator[Any]):
    """Fallback evaluator for unknown legacy evaluator types."""

    pass


class UnknownEvaluatorConfig(BaseEvaluatorConfig[Any]):
    """Fallback config for unknown evaluator types."""

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class UnknownCodedEvaluator(BaseEvaluator[Any, Any, Any]):
    """Fallback evaluator for unknown coded evaluator types."""

    pass


def legacy_evaluator_discriminator(data: Any) -> str:
    """Determine the specific legacy evaluator type based on category and type fields."""
    if isinstance(data, dict):
        category = data.get("category")
        evaluator_type = data.get("type")
        match category:
            case LegacyEvaluatorCategory.LlmAsAJudge:
                return "LegacyLLMEvaluator"
            case LegacyEvaluatorCategory.Trajectory:
                return "LegacyTrajectoryEvaluator"
            case LegacyEvaluatorCategory.Deterministic:
                match evaluator_type:
                    case LegacyEvaluatorType.Equals:
                        return "LegacyEqualsEvaluator"
                    case LegacyEvaluatorType.JsonSimilarity:
                        return "LegacyJsonSimilarityEvaluator"
                    case _:
                        return "LegacyUnknownEvaluator"
            case _:
                return "LegacyUnknownEvaluator"
    else:
        return "LegacyUnknownLegacyEvaluator"


LegacyEvaluator = Annotated[
    Union[
        Annotated[
            LegacyLlmAsAJudgeEvaluator,
            Tag("LegacyLLMEvaluator"),
        ],
        Annotated[
            LegacyTrajectoryEvaluator,
            Tag("LegacyTrajectoryEvaluator"),
        ],
        Annotated[
            LegacyExactMatchEvaluator,
            Tag("LegacyEqualsEvaluator"),
        ],
        Annotated[
            LegacyJsonSimilarityEvaluator,
            Tag("LegacyJsonSimilarityEvaluator"),
        ],
        Annotated[
            UnknownLegacyEvaluator,
            Tag("LegacyUnknownEvaluator"),
        ],
    ],
    Field(discriminator=Discriminator(legacy_evaluator_discriminator)),
]


def coded_evaluator_discriminator(data: Any) -> str:
    """Determine the specific coded evaluator type based on evaluatorTypeId field."""
    if isinstance(data, dict):
        evaluator_type_id = data.get("evaluatorTypeId")
        match evaluator_type_id:
            case EvaluatorType.CONTAINS:
                return "ContainsEvaluator"
            case EvaluatorType.EXACT_MATCH:
                return "ExactMatchEvaluator"
            case EvaluatorType.JSON_SIMILARITY:
                return "JsonSimilarityEvaluator"
            case EvaluatorType.LLM_JUDGE_OUTPUT_SEMANTIC_SIMILARITY:
                return "LLMJudgeOutputEvaluator"
            case EvaluatorType.LLM_JUDGE_OUTPUT_STRICT_JSON_SIMILARITY:
                return "LLMJudgeStrictJSONSimilarityOutputEvaluator"
            case EvaluatorType.LLM_JUDGE_TRAJECTORY_SIMILARITY:
                return "LLMJudgeTrajectoryEvaluator"
            case EvaluatorType.LLM_JUDGE_TRAJECTORY_SIMULATION:
                return "LLMJudgeTrajectorySimulationEvaluator"
            case EvaluatorType.TOOL_CALL_ARGS:
                return "ToolCallArgsEvaluator"
            case EvaluatorType.TOOL_CALL_COUNT:
                return "ToolCallCountEvaluator"
            case EvaluatorType.TOOL_CALL_ORDER:
                return "ToolCallOrderEvaluator"
            case EvaluatorType.TOOL_CALL_OUTPUT:
                return "ToolCallOutputEvaluator"
            case _:
                return "UnknownEvaluator"
    else:
        return "UnknownEvaluator"


CodedEvaluator = Annotated[
    Union[
        Annotated[
            ContainsEvaluator,
            Tag("ContainsEvaluator"),
        ],
        Annotated[
            ExactMatchEvaluator,
            Tag("ExactMatchEvaluator"),
        ],
        Annotated[
            JsonSimilarityEvaluator,
            Tag("JsonSimilarityEvaluator"),
        ],
        Annotated[
            LLMJudgeOutputEvaluator,
            Tag("LLMJudgeOutputEvaluator"),
        ],
        Annotated[
            LLMJudgeStrictJSONSimilarityOutputEvaluator,
            Tag("LLMJudgeStrictJSONSimilarityOutputEvaluator"),
        ],
        Annotated[
            LLMJudgeTrajectoryEvaluator,
            Tag("LLMJudgeTrajectoryEvaluator"),
        ],
        Annotated[
            ToolCallArgsEvaluator,
            Tag("ToolCallArgsEvaluator"),
        ],
        Annotated[
            ToolCallCountEvaluator,
            Tag("ToolCallCountEvaluator"),
        ],
        Annotated[
            ToolCallOrderEvaluator,
            Tag("ToolCallOrderEvaluator"),
        ],
        Annotated[
            ToolCallOutputEvaluator,
            Tag("ToolCallOutputEvaluator"),
        ],
        Annotated[
            LLMJudgeTrajectorySimulationEvaluator,
            Tag("LLMJudgeTrajectorySimulationEvaluator"),
        ],
        Annotated[
            UnknownCodedEvaluator,
            Tag("UnknownEvaluator"),
        ],
    ],
    Field(discriminator=Discriminator(coded_evaluator_discriminator)),
]


def evaluator_discriminator(data: Any) -> str:
    """Determine the specific evaluator type (legacy vs coded) based on presence of version field."""
    if "version" in data:
        return "CodedEvaluator"
    else:
        return "LegacyEvaluator"


Evaluator = Annotated[
    Union[
        Annotated[
            LegacyEvaluator,
            Tag("LegacyEvaluator"),
        ],
        Annotated[
            CodedEvaluator,
            Tag("CodedEvaluator"),
        ],
    ],
    Field(discriminator=Discriminator(evaluator_discriminator)),
]
