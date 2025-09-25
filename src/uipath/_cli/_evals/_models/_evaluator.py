from typing import Annotated, Any, Union

from pydantic import BaseModel, ConfigDict, Discriminator, Field, Tag

from uipath.eval.models.models import EvaluatorCategory, EvaluatorType


class EvaluatorBaseParams(BaseModel):
    """Parameters for initializing the base evaluator."""

    id: str
    name: str
    description: str
    category: EvaluatorCategory = Field(..., alias="category")
    evaluator_type: EvaluatorType = Field(..., alias="type")
    created_at: str = Field(..., alias="createdAt")
    updated_at: str = Field(..., alias="updatedAt")
    target_output_key: str = Field(..., alias="targetOutputKey")
    file_name: str = Field(..., alias="fileName")


class LLMEvaluatorParams(EvaluatorBaseParams):
    prompt: str = Field(..., alias="prompt")
    model: str = Field(..., alias="model")

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
        if (
            category == EvaluatorCategory.LlmAsAJudge
            or evaluator_type == EvaluatorType.Trajectory
        ):
            return "LLMEvaluatorParams"
    return "UnknownEvaluatorParams"


Evaluator = Annotated[
    Union[
        Annotated[
            LLMEvaluatorParams,
            Tag("LLMEvaluatorParams"),
        ],
        Annotated[
            UnknownEvaluatorParams,
            Tag("UnknownEvaluatorParams"),
        ],
    ],
    Field(discriminator=Discriminator(evaluator_discriminator)),
]
