from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Discriminator, Field, Tag

from uipath.eval.evaluators.base_evaluator import BaseEvaluatorConfig
from uipath.eval.evaluators.contains_evaluator import ContainsEvaluatorConfig
from uipath.eval.evaluators.exact_match_evaluator import ExactMatchEvaluatorConfig
from uipath.eval.evaluators.json_similarity_evaluator import (
    JsonSimilarityEvaluatorConfig,
)
from uipath.eval.evaluators.llm_judge_output_evaluator import (
    LLMJudgeOutputEvaluatorConfig,
    LLMJudgeStrictJSONSimilarityOutputEvaluatorConfig,
)
from uipath.eval.evaluators.llm_judge_trajectory_evaluator import (
    LLMJudgeTrajectoryEvaluatorConfig,
    LLMJudgeTrajectorySimulationEvaluatorConfig,
)
from uipath.eval.evaluators.tool_call_args_evaluator import (
    ToolCallArgsEvaluatorConfig,
)
from uipath.eval.evaluators.tool_call_count_evaluator import (
    ToolCallCountEvaluatorConfig,
)
from uipath.eval.evaluators.tool_call_order_evaluator import (
    ToolCallOrderEvaluatorConfig,
)
from uipath.eval.evaluators.tool_call_output_evaluator import (
    ToolCallOutputEvaluatorConfig,
)
from uipath.eval.models import (
    EvaluatorType,
    LegacyEvaluatorCategory,
    LegacyEvaluatorType,
)


class LegacyEvaluatorBaseParams(BaseModel):
    """Parameters for initializing the base evaluator."""

    id: str
    name: str
    description: str
    evaluator_type: LegacyEvaluatorType = Field(..., alias="type")
    created_at: str = Field(..., alias="createdAt")
    updated_at: str = Field(..., alias="updatedAt")
    target_output_key: str = Field(..., alias="targetOutputKey")
    file_name: str = Field(..., alias="fileName")


class LegacyLLMEvaluatorParams(LegacyEvaluatorBaseParams):
    category: Literal[LegacyEvaluatorCategory.LlmAsAJudge] = Field(
        ..., alias="category"
    )
    prompt: str = Field(..., alias="prompt")
    model: str = Field(..., alias="model")

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class LegacyTrajectoryEvaluatorParams(LegacyEvaluatorBaseParams):
    category: Literal[LegacyEvaluatorCategory.Trajectory] = Field(..., alias="category")
    prompt: str = Field(..., alias="prompt")
    model: str = Field(..., alias="model")

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class LegacyEqualsEvaluatorParams(LegacyEvaluatorBaseParams):
    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class LegacyJsonSimilarityEvaluatorParams(LegacyEvaluatorBaseParams):
    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class LegacyUnknownEvaluatorParams(LegacyEvaluatorBaseParams):
    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


def legacy_evaluator_discriminator(data: Any) -> str:
    if isinstance(data, dict):
        category = data.get("category")
        evaluator_type = data.get("type")
        match category:
            case LegacyEvaluatorCategory.LlmAsAJudge:
                return "LegacyLLMEvaluatorParams"
            case LegacyEvaluatorCategory.Trajectory:
                return "LegacyTrajectoryEvaluatorParams"
            case LegacyEvaluatorCategory.Deterministic:
                match evaluator_type:
                    case LegacyEvaluatorType.Equals:
                        return "LegacyEqualsEvaluatorParams"
                    case LegacyEvaluatorType.JsonSimilarity:
                        return "LegacyJsonSimilarityEvaluatorParams"
                    case _:
                        return "LegacyUnknownEvaluatorParams"
            case _:
                return "LegacyUnknownEvaluatorParams"
    else:
        return "LegacyUnknownLegacyEvaluatorParams"


LegacyEvaluator = Annotated[
    Union[
        Annotated[
            LegacyLLMEvaluatorParams,
            Tag("LegacyLLMEvaluatorParams"),
        ],
        Annotated[
            LegacyTrajectoryEvaluatorParams,
            Tag("LegacyTrajectoryEvaluatorParams"),
        ],
        Annotated[
            LegacyEqualsEvaluatorParams,
            Tag("LegacyEqualsEvaluatorParams"),
        ],
        Annotated[
            LegacyJsonSimilarityEvaluatorParams,
            Tag("LegacyJsonSimilarityEvaluatorParams"),
        ],
        Annotated[
            LegacyUnknownEvaluatorParams,
            Tag("LegacyUnknownEvaluatorParams"),
        ],
    ],
    Field(discriminator=Discriminator(legacy_evaluator_discriminator)),
]


class UnknownEvaluatorConfig(BaseEvaluatorConfig[Any]):
    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


def evaluator_config_discriminator(data: Any) -> str:
    if isinstance(data, dict):
        evaluator_type_id = data.get("evaluatorTypeId")
        match evaluator_type_id:
            case EvaluatorType.CONTAINS:
                return "ContainsEvaluatorConfig"
            case EvaluatorType.EXACT_MATCH:
                return "ExactMatchEvaluatorConfig"
            case EvaluatorType.JSON_SIMILARITY:
                return "JsonSimilarityEvaluatorConfig"
            case EvaluatorType.LLM_JUDGE_OUTPUT_SEMANTIC_SIMILARITY:
                return "LLMJudgeOutputEvaluatorConfig"
            case EvaluatorType.LLM_JUDGE_OUTPUT_STRICT_JSON_SIMILARITY:
                return "LLMJudgeStrictJSONSimilarityOutputEvaluatorConfig"
            case EvaluatorType.LLM_JUDGE_TRAJECTORY_SIMILARITY:
                return "LLMJudgeTrajectoryEvaluatorConfig"
            case EvaluatorType.LLM_JUDGE_TRAJECTORY_SIMULATION:
                return "LLMJudgeTrajectorySimulationEvaluatorConfig"
            case EvaluatorType.TOOL_CALL_ARGS:
                return "ToolCallArgsEvaluatorConfig"
            case EvaluatorType.TOOL_CALL_COUNT:
                return "ToolCallCountEvaluatorConfig"
            case EvaluatorType.TOOL_CALL_ORDER:
                return "ToolCallOrderEvaluatorConfig"
            case EvaluatorType.TOOL_CALL_OUTPUT:
                return "ToolCallOutputEvaluatorConfig"
            case _:
                return "UnknownEvaluatorConfig"
    else:
        return "UnknownEvaluatorConfig"


EvaluatorConfig = Annotated[
    Union[
        Annotated[
            ContainsEvaluatorConfig,
            Tag("ContainsEvaluatorConfig"),
        ],
        Annotated[
            ExactMatchEvaluatorConfig,
            Tag("ExactMatchEvaluatorConfig"),
        ],
        Annotated[
            JsonSimilarityEvaluatorConfig,
            Tag("JsonSimilarityEvaluatorConfig"),
        ],
        Annotated[
            LLMJudgeOutputEvaluatorConfig,
            Tag("LLMJudgeOutputEvaluatorConfig"),
        ],
        Annotated[
            LLMJudgeStrictJSONSimilarityOutputEvaluatorConfig,
            Tag("LLMJudgeStrictJSONSimilarityOutputEvaluatorConfig"),
        ],
        Annotated[
            LLMJudgeTrajectoryEvaluatorConfig,
            Tag("LLMJudgeTrajectoryEvaluatorConfig"),
        ],
        Annotated[
            ToolCallArgsEvaluatorConfig,
            Tag("ToolCallArgsEvaluatorConfig"),
        ],
        Annotated[
            ToolCallCountEvaluatorConfig,
            Tag("ToolCallCountEvaluatorConfig"),
        ],
        Annotated[
            ToolCallOrderEvaluatorConfig,
            Tag("ToolCallOrderEvaluatorConfig"),
        ],
        Annotated[
            ToolCallOutputEvaluatorConfig,
            Tag("ToolCallOutputEvaluatorConfig"),
        ],
        Annotated[
            LLMJudgeTrajectorySimulationEvaluatorConfig,
            Tag("LLMJudgeTrajectorySimulationEvaluatorConfig"),
        ],
        Annotated[
            UnknownEvaluatorConfig,
            Tag("UnknownEvaluatorConfig"),
        ],
    ],
    Field(discriminator=Discriminator(evaluator_config_discriminator)),
]
