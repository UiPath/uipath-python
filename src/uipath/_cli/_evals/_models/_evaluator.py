from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Discriminator, Field, Tag

from uipath.eval.coded_evaluators.base_evaluator import BaseEvaluatorConfig
from uipath.eval.coded_evaluators.contains_evaluator import ContainsEvaluatorConfig
from uipath.eval.coded_evaluators.exact_match_evaluator import ExactMatchEvaluatorConfig
from uipath.eval.coded_evaluators.json_similarity_evaluator import (
    JsonSimilarityEvaluatorConfig,
)
from uipath.eval.coded_evaluators.llm_judge_output_evaluator import (
    LLMJudgeOutputEvaluatorConfig,
    LLMJudgeStrictJSONSimilarityOutputEvaluatorConfig,
)
from uipath.eval.models.models import (
    EvaluatorType,
    LegacyEvaluatorCategory,
    LegacyEvaluatorType,
)


class EvaluatorBaseParams(BaseModel):
    """Parameters for initializing the base evaluator."""

    id: str
    name: str
    description: str
    evaluator_type: LegacyEvaluatorType = Field(..., alias="type")
    created_at: str = Field(..., alias="createdAt")
    updated_at: str = Field(..., alias="updatedAt")
    target_output_key: str = Field(..., alias="targetOutputKey")
    file_name: str = Field(..., alias="fileName")


class LLMEvaluatorParams(EvaluatorBaseParams):
    category: Literal[LegacyEvaluatorCategory.LlmAsAJudge] = Field(
        ..., alias="category"
    )
    prompt: str = Field(..., alias="prompt")
    model: str = Field(..., alias="model")

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class TrajectoryEvaluatorParams(EvaluatorBaseParams):
    category: Literal[LegacyEvaluatorCategory.Trajectory] = Field(..., alias="category")
    prompt: str = Field(..., alias="prompt")
    model: str = Field(..., alias="model")

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class EqualsEvaluatorParams(EvaluatorBaseParams):
    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class JsonSimilarityEvaluatorParams(EvaluatorBaseParams):
    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class UnknownEvaluatorParams(EvaluatorBaseParams):
    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


def evaluator_discriminator(data: Any) -> str:
    if isinstance(data, dict):
        category = data.get("category")
        evaluator_type = data.get("type")
        match category:
            case LegacyEvaluatorCategory.LlmAsAJudge:
                return "LLMEvaluatorParams"
            case LegacyEvaluatorCategory.Trajectory:
                return "TrajectoryEvaluatorParams"
            case LegacyEvaluatorCategory.Deterministic:
                match evaluator_type:
                    case LegacyEvaluatorType.Equals:
                        return "EqualsEvaluatorParams"
                    case LegacyEvaluatorType.JsonSimilarity:
                        return "JsonSimilarityEvaluatorParams"
                    case _:
                        return "UnknownEvaluatorParams"
            case _:
                return "UnknownEvaluatorParams"
    else:
        return "UnknownEvaluatorParams"


Evaluator = Annotated[
    Union[
        Annotated[
            LLMEvaluatorParams,
            Tag("LLMEvaluatorParams"),
        ],
        Annotated[
            TrajectoryEvaluatorParams,
            Tag("TrajectoryEvaluatorParams"),
        ],
        Annotated[
            EqualsEvaluatorParams,
            Tag("EqualsEvaluatorParams"),
        ],
        Annotated[
            JsonSimilarityEvaluatorParams,
            Tag("JsonSimilarityEvaluatorParams"),
        ],
        Annotated[
            UnknownEvaluatorParams,
            Tag("UnknownEvaluatorParams"),
        ],
    ],
    Field(discriminator=Discriminator(evaluator_discriminator)),
]


class UnknownEvaluatorConfig(BaseEvaluatorConfig[Any]):
    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


def legacy_evaluator_discriminator(data: Any) -> str:
    if isinstance(data, dict):
        category = data.get("category")
        evaluator_type = data.get("type")
        match category:
            case LegacyEvaluatorCategory.LlmAsAJudge:
                return "LLMEvaluatorParams"
            case LegacyEvaluatorCategory.Trajectory:
                return "TrajectoryEvaluatorParams"
            case LegacyEvaluatorCategory.Deterministic:
                match evaluator_type:
                    case LegacyEvaluatorType.Equals:
                        return "EqualsEvaluatorParams"
                    case LegacyEvaluatorType.JsonSimilarity:
                        return "JsonSimilarityEvaluatorParams"
                    case _:
                        return "UnknownEvaluatorParams"
            case _:
                return "UnknownEvaluatorParams"
    else:
        return "UnknownEvaluatorParams"


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
            case _:
                return "UnknownEvaluatorConfig"
    else:
        return "UnknownEvaluatorConfig"


LegacyEvaluator = Annotated[
    Union[
        Annotated[
            LLMEvaluatorParams,
            Tag("LLMEvaluatorParams"),
        ],
        Annotated[
            TrajectoryEvaluatorParams,
            Tag("TrajectoryEvaluatorParams"),
        ],
        Annotated[
            EqualsEvaluatorParams,
            Tag("EqualsEvaluatorParams"),
        ],
        Annotated[
            JsonSimilarityEvaluatorParams,
            Tag("JsonSimilarityEvaluatorParams"),
        ],
        Annotated[
            UnknownEvaluatorParams,
            Tag("UnknownEvaluatorParams"),
        ],
    ],
    Field(discriminator=Discriminator(legacy_evaluator_discriminator)),
]

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
            UnknownEvaluatorConfig,
            Tag("UnknownEvaluatorConfig"),
        ],
    ],
    Field(discriminator=Discriminator(evaluator_config_discriminator)),
]
