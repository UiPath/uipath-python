from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class BaseModelWithDefaultConfig(BaseModel):
    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        populate_by_name=True,
        extra="allow",
    )


class BindingResourceValue(BaseModelWithDefaultConfig):
    default_value: str = Field(..., alias="defaultValue")
    is_expression: bool = Field(..., alias="isExpression")
    display_name: str = Field(..., alias="displayName")
    description: str | None = Field(default=None, alias="description")
    property_name: str | None = Field(default=None, alias="propertyName")


# TODO: create stronger binding resource definition with discriminator based on resource enum.
class BindingResource(BaseModelWithDefaultConfig):
    resource: str = Field(..., alias="resource")
    key: str = Field(..., alias="key")
    value: dict[str, BindingResourceValue] = Field(..., alias="value")
    metadata: dict[str, Any] | None = Field(alias="metadata", default=None)


class Bindings(BaseModelWithDefaultConfig):
    version: str = Field(..., alias="version")
    resources: list[BindingResource] = Field(..., alias="resources")


class EntryPoint(BaseModelWithDefaultConfig):
    file_path: str = Field(..., alias="filePath")
    unique_id: str = Field(..., alias="uniqueId")
    type: str = Field(..., alias="type")
    input: dict[str, Any] = Field(..., alias="input")
    output: dict[str, Any] = Field(..., alias="output")
    graph: dict[str, Any] | None = Field(default=None, alias="graph")
    metadata: dict[str, Any] | None = Field(default=None, alias="metadata")


class EntryPoints(BaseModelWithDefaultConfig):
    schema_: str = Field(
        default="https://cloud.uipath.com/draft/2024-12/entry-point",
        alias="$schema",
    )
    id_: str = Field(default="entry-points.json", alias="$id")
    entrypoints: list[EntryPoint] = Field(..., alias="entryPoints")


class RuntimeInternalArguments(BaseModelWithDefaultConfig):
    resource_overwrites: dict[str, Any] = Field(..., alias="resourceOverwrites")


class RuntimeArguments(BaseModelWithDefaultConfig):
    internal_arguments: Optional[RuntimeInternalArguments] = Field(
        default=None, alias="internalArguments"
    )
