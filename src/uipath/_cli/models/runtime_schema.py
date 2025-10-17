from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

COMMON_MODEL_SCHEMA = ConfigDict(
    validate_by_name=True,
    validate_by_alias=True,
    use_enum_values=True,
    arbitrary_types_allowed=True,
    extra="allow",
)


class EntrypointType(str, Enum):
    AGENT = "agent"


class Entrypoint(BaseModel):
    file_path: str = Field(..., alias="filePath")
    unique_id: str = Field(..., alias="uniqueId")
    type: EntrypointType = EntrypointType.AGENT
    input: Dict[str, Any] = Field(..., alias="input")
    output: Dict[str, Any] = Field(..., alias="output")

    model_config = COMMON_MODEL_SCHEMA


class BindingResourceValue(BaseModel):
    default_value: str = Field(..., alias="defaultValue")
    is_expression: bool = Field(..., alias="isExpression")
    display_name: str = Field(..., alias="displayName")

    model_config = COMMON_MODEL_SCHEMA


# TODO: create stronger binding resource definition with discriminator based on resource enum.
class BindingResource(BaseModel):
    resource: str = Field(..., alias="resource")
    key: str = Field(..., alias="key")
    value: dict[str, BindingResourceValue] = Field(..., alias="value")
    metadata: Any = Field(..., alias="metadata")

    model_config = COMMON_MODEL_SCHEMA


class Binding(BaseModel):
    version: str = Field(..., alias="version")
    resources: List[BindingResource] = Field(..., alias="resources")

    model_config = COMMON_MODEL_SCHEMA


class RuntimeInternalArguments(BaseModel):
    resource_overwrites: dict[str, Any] = Field(..., alias="resourceOverwrites")

    model_config = COMMON_MODEL_SCHEMA


class RuntimeArguments(BaseModel):
    internal_arguments: Optional[RuntimeInternalArguments] = Field(
        default=None, alias="internalArguments"
    )

    model_config = COMMON_MODEL_SCHEMA


class RuntimeSchema(BaseModel):
    runtime: Optional[RuntimeArguments] = Field(default=None, alias="runtime")
    entrypoints: List[Entrypoint] = Field(..., alias="entryPoints")
    bindings: Binding = Field(..., alias="bindings")

    model_config = COMMON_MODEL_SCHEMA
