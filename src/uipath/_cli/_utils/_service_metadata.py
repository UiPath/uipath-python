"""Service metadata models using Pydantic.

This module defines the metadata structure for CLI service command generation.
All models are immutable (frozen) to prevent accidental modification after creation.

The metadata describes:
- Service identification (name, resource type)
- CRUD operation parameters
- Command configuration (confirmation, dry-run support)

Example:
    >>> from ._service_metadata import ServiceMetadata, CreateParameter
    >>>
    >>> BUCKETS_METADATA = ServiceMetadata(
    ...     service_name="buckets",
    ...     service_attr="buckets",
    ...     resource_type="Bucket",
    ...     create_params={
    ...         "description": CreateParameter(
    ...             type="str",
    ...             required=False,
    ...             help="Bucket description",
    ...         )
    ...     },
    ... )
"""

from typing import Any

from pydantic import BaseModel, Field, model_validator


class CreateParameter(BaseModel):
    """Metadata for a single create command parameter.

    This defines how a parameter should appear in the CLI command.

    Attributes:
        type: Type name from TYPE_REGISTRY (e.g., "str", "int", "bool", "float")
        required: Whether the parameter is required (default: False)
        help: Help text shown in --help output
        default: Default value if not provided by user
        option_name: CLI option name (default: derived from field name)

    Example:
        >>> description_param = CreateParameter(
        ...     type="str",
        ...     required=False,
        ...     help="Resource description",
        ...     default=None,
        ... )
    """

    type: str
    required: bool = False
    help: str = ""
    default: Any = None
    option_name: str | None = None

    class Config:
        """Pydantic configuration."""

        frozen = True


class DeleteCommandConfig(BaseModel):
    """Configuration for delete command behavior.

    Attributes:
        confirmation_required: Whether to require --confirm flag (default: True)
        dry_run_supported: Whether to support --dry-run flag (default: True)
        confirmation_prompt: Custom confirmation prompt template

    Example:
        >>> delete_config = DeleteCommandConfig(
        ...     confirmation_required=True,
        ...     dry_run_supported=True,
        ...     confirmation_prompt="Delete {resource} '{identifier}'?",
        ... )
    """

    confirmation_required: bool = True
    dry_run_supported: bool = True
    confirmation_prompt: str | None = None

    class Config:
        """Pydantic configuration."""

        frozen = True


class ExistsCommandConfig(BaseModel):
    """Configuration for exists command behavior.

    Attributes:
        identifier_arg_name: Name of the identifier argument (default: "name")
        return_format: Format of the return value ("bool", "dict", "text")

    Example:
        >>> exists_config = ExistsCommandConfig(
        ...     identifier_arg_name="key",
        ...     return_format="dict",
        ... )
    """

    identifier_arg_name: str = "name"
    return_format: str = "dict"  # "bool", "dict", or "text"

    class Config:
        """Pydantic configuration."""

        frozen = True


class ServiceMetadata(BaseModel):
    """Complete metadata for a service's CLI commands.

    This metadata is used by ServiceCLIGenerator to auto-generate standard
    CRUD commands (list, retrieve, create, delete, exists).

    Attributes:
        service_name: CLI command group name (e.g., "buckets", "assets")
        service_attr: Attribute name on UiPath client (e.g., client.buckets)
        resource_type: Human-readable resource name (e.g., "Bucket", "Asset")
        resource_plural: Plural form of resource type (auto-generated if not provided)
        create_params: Dictionary of parameters for create command
        delete_cmd: Configuration for delete command behavior
        exists_cmd: Configuration for exists command behavior
        list_supports_filters: Whether list command supports additional filters
        retrieve_identifier: Name of the identifier argument for retrieve

    Example:
        >>> metadata = ServiceMetadata(
        ...     service_name="buckets",
        ...     service_attr="buckets",
        ...     resource_type="Bucket",
        ...     create_params={
        ...         "description": CreateParameter(
        ...             type="str",
        ...             required=False,
        ...             help="Bucket description",
        ...         )
        ...     },
        ... )
        >>> metadata.resource_plural
        'Buckets'
    """

    service_name: str
    service_attr: str
    resource_type: str
    resource_plural: str | None = None
    create_params: dict[str, CreateParameter] = Field(default_factory=dict)
    delete_cmd: DeleteCommandConfig = Field(default_factory=DeleteCommandConfig)
    exists_cmd: ExistsCommandConfig = Field(default_factory=ExistsCommandConfig)
    list_supports_filters: bool = False
    retrieve_identifier: str = "name"

    class Config:
        """Pydantic configuration."""

        frozen = True

    @model_validator(mode="after")
    def set_defaults(self) -> "ServiceMetadata":
        """Set default values that depend on other fields.

        This validator runs after model creation to set derived defaults:
        - resource_plural from resource_type
        - delete_cmd defaults if not explicitly set

        Note:
            Since the model is frozen, we use object.__setattr__ to modify fields.
        """
        if self.resource_plural is None:
            object.__setattr__(self, "resource_plural", f"{self.resource_type}s")

        return self

    def validate_types(self) -> None:
        """Validate that all parameter types are in TYPE_REGISTRY.

        Raises:
            ValueError: If any parameter type is not registered

        Example:
            >>> metadata = ServiceMetadata(
            ...     service_name="test",
            ...     service_attr="test",
            ...     resource_type="Test",
            ...     create_params={
            ...         "invalid": CreateParameter(type="InvalidType", required=False)
            ...     },
            ... )
            >>> metadata.validate_types()
            Traceback (most recent call last):
            ...
            ValueError: Invalid type 'InvalidType' for parameter 'invalid' in service 'test'...
        """
        from ._type_registry import is_valid_type

        for param_name, param in self.create_params.items():
            if not is_valid_type(param.type):
                from ._type_registry import TYPE_REGISTRY

                valid_types = ", ".join(sorted(TYPE_REGISTRY.keys()))
                raise ValueError(
                    f"Invalid type '{param.type}' for parameter '{param_name}' "
                    f"in service '{self.service_name}'. Valid types: {valid_types}"
                )


__all__ = [
    "CreateParameter",
    "DeleteCommandConfig",
    "ExistsCommandConfig",
    "ServiceMetadata",
]
