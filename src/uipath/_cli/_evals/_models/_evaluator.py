from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Discriminator, Field, Tag

from uipath.eval.models.models import EvaluatorCategory, EvaluatorType


class EvaluatorBaseParams(BaseModel):
    """Parameters for initializing the base evaluator."""

    id: str
    name: str
    description: str
    evaluator_type: EvaluatorType = Field(..., alias="type")
    created_at: str = Field(..., alias="createdAt")
    updated_at: str = Field(..., alias="updatedAt")
    target_output_key: str = Field(..., alias="targetOutputKey")
    file_name: str = Field(..., alias="fileName")


class LLMEvaluatorParams(EvaluatorBaseParams):
    category: Literal[EvaluatorCategory.LlmAsAJudge] = Field(..., alias="category")
    prompt: str = Field(..., alias="prompt")
    model: str = Field(..., alias="model")

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class TrajectoryEvaluatorParams(EvaluatorBaseParams):
    category: Literal[EvaluatorCategory.Trajectory] = Field(..., alias="category")
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
            case EvaluatorCategory.LlmAsAJudge:
                return "LLMEvaluatorParams"
            case EvaluatorCategory.Trajectory:
                return "TrajectoryEvaluatorParams"
            case EvaluatorCategory.Deterministic:
                match evaluator_type:
                    case EvaluatorType.Equals:
                        return "EqualsEvaluatorParams"
                    case EvaluatorType.JsonSimilarity:
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
