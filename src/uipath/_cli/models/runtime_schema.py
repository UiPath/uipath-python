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


# TODO: create stronger binding resource definition with discriminator based on resource enum.
class BindingResource(BaseModelWithDefaultConfig):
    resource: str = Field(..., alias="resource")
    key: str = Field(..., alias="key")
    value: dict[str, BindingResourceValue] = Field(..., alias="value")
    metadata: dict[str, Any] | None = Field(alias="metadata", default=None)


class Bindings(BaseModelWithDefaultConfig):
    version: str = Field(..., alias="version")
    resources: list[BindingResource] = Field(..., alias="resources")


class RuntimeInternalArguments(BaseModelWithDefaultConfig):
    resource_overwrites: dict[str, Any] = Field(..., alias="resourceOverwrites")


class RuntimeArguments(BaseModelWithDefaultConfig):
    internal_arguments: Optional[RuntimeInternalArguments] = Field(
        default=None, alias="internalArguments"
    )
