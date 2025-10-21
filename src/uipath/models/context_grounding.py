from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ContextGroundingMetadata(BaseModel):
    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
    )
    operation_id: str = Field(alias="operation_id")
    strategy: str = Field(alias="strategy")


class ContextGroundingQueryResponse(BaseModel):
    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
    )
    source: str = Field(alias="source")
    page_number: str = Field(alias="page_number")
    content: str = Field(alias="content")
    metadata: ContextGroundingMetadata = Field(alias="metadata")
    source_document_id: Optional[str] = Field(default=None, alias="source_document_id")
    caption: Optional[str] = Field(default=None, alias="caption")
    score: Optional[float] = Field(default=None, alias="score")
    reference: Optional[str] = Field(default=None, alias="reference")
