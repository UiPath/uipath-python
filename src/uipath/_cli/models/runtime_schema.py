from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

COMMON_MODEL_SCHEMA = ConfigDict(
    validate_by_name=True,
    validate_by_alias=True,
    use_enum_values=True,
    arbitrary_types_allowed=True,
    extra="allow",
)


class Entrypoint(BaseModel):
    file_path: str = Field(..., alias="filePath")
    unique_id: str = Field(..., alias="uniqueId")
    type: str = Field(..., alias="type")
    input: Dict[str, Any] = Field(..., alias="input")
    output: Dict[str, Any] = Field(..., alias="output")

    model_config = COMMON_MODEL_SCHEMA


class Entrypoints(BaseModel):
    entry_points: List[Entrypoint] = Field(..., alias="entryPoints")

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


class Bindings(BaseModel):
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

    # TODO: left for backward compatibility with uipath-langchain and uipath-llamaindex libraries. should be removed on 2.2.x
    entrypoints: Optional[List[Entrypoint]] = Field(default=None, alias="entryPoints")

    # TODO: left for backward compatibility with uipath-langchain and uipath-llamaindex libraries. should be removed on 2.2.x
    bindings: Optional[Bindings] = Field(
        default=Bindings(version="2.0", resources=[]), alias="bindings"
    )
    settings: Optional[Dict[str, Any]] = Field(default=None, alias="settings")

    model_config = COMMON_MODEL_SCHEMA
