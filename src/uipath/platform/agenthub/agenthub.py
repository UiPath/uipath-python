"""AgentHub response payload models."""

from pydantic import BaseModel, ConfigDict, Field


class LlmModel(BaseModel):
    """Model representing an available LLM model."""

    model_name: str = Field(..., alias="modelName")
    vendor: str | None = Field(default=None)

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
    )
