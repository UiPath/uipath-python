import functools
import inspect
from abc import ABC, abstractmethod
from contextvars import ContextVar, Token
from typing import (
    Annotated,
    Any,
    Callable,
    Coroutine,
    Literal,
    Optional,
    TypeVar,
    Union,
)

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, TypeAdapter

T = TypeVar("T")


class ResourceOverwrite(BaseModel, ABC):
    """Abstract base class for resource overwrites.

    Subclasses must implement properties to provide resource and folder identifiers
    appropriate for their resource type.
    """

    model_config = ConfigDict(populate_by_name=True)

    @property
    @abstractmethod
    def resource_identifier(self) -> str:
        """The identifier used to reference this resource."""
        pass

    @property
    @abstractmethod
    def folder_identifier(self) -> str:
        """The folder location identifier for this resource."""
        pass


class GenericResourceOverwrite(ResourceOverwrite):
    resource_type: Literal["process", "index", "app", "asset", "bucket"]
    name: str = Field(alias="name")
    folder_path: str = Field(alias="folderPath")

    @property
    def resource_identifier(self) -> str:
        return self.name

    @property
    def folder_identifier(self) -> str:
        return self.folder_path


class ConnectionResourceOverwrite(ResourceOverwrite):
    resource_type: Literal["connection"]
    # In eval context, studio web provides "ConnectionId".
    connection_id: str = Field(
        alias="connectionId",
        validation_alias=AliasChoices("connectionId", "ConnectionId"),
    )
    folder_key: str = Field(alias="folderKey")

    model_config = ConfigDict(
        populate_by_name=True,
        extra="ignore",
    )

    @property
    def resource_identifier(self) -> str:
        return self.connection_id

    @property
    def folder_identifier(self) -> str:
        return self.folder_key


ResourceOverwriteUnion = Annotated[
    Union[GenericResourceOverwrite, ConnectionResourceOverwrite],
    Field(discriminator="resource_type"),
]


class ResourceOverwriteParser:
    """Parser for resource overwrite configurations.

    Handles parsing of resource overwrites from key-value pairs where the key
    contains the resource type prefix (e.g., "process.name", "connection.key").
    """

    _adapter: TypeAdapter[ResourceOverwriteUnion] = TypeAdapter(ResourceOverwriteUnion)

    @classmethod
    def parse(cls, key: str, value: dict[str, Any]) -> ResourceOverwrite:
        """Parse a resource overwrite from a key-value pair.

        Extracts the resource type from the key prefix and injects it into the value
        for discriminated union validation.

        Args:
            key: The resource key (e.g., "process.MyProcess", "connection.abc-123")
            value: The resource data dictionary

        Returns:
            The appropriate ResourceOverwrite subclass instance
        """
        resource_type = key.split(".")[0]
        value_with_type = {"resource_type": resource_type, **value}
        return cls._adapter.validate_python(value_with_type)


_resource_overwrites: ContextVar[Optional[dict[str, ResourceOverwrite]]] = ContextVar(
    "resource_overwrites", default=None
)


class ResourceOverwritesContext:
    def __init__(
        self,
        get_overwrites_callable: Callable[
            [], Coroutine[Any, Any, dict[str, ResourceOverwrite]]
        ],
    ):
        self.get_overwrites_callable = get_overwrites_callable
        self._token: Optional[Token[Optional[dict[str, ResourceOverwrite]]]] = None
        self.overwrites_count = 0

    async def __aenter__(self) -> "ResourceOverwritesContext":
        overwrites = await self.get_overwrites_callable()
        self._token = _resource_overwrites.set(overwrites)
        self.overwrites_count = len(overwrites)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._token:
            _resource_overwrites.reset(self._token)


def resource_override(
    resource_type: str,
    resource_identifier: str = "name",
    folder_identifier: str = "folder_path",
) -> Callable[..., Any]:
    """Decorator for applying resource overrides for an overridable resource.

    It checks the current ContextVar to identify the requested overrides and, if any key matches, it invokes the decorated function
    with the extracted resource and folder identifiers.

    Args:
        resource_type: Type of resource to check for overrides (e.g., "asset", "bucket")
        resource_identifier: Key name for the resource ID in override data (default: "name")
        folder_identifier: Key name for the folder path in override data (default: "folder_path")

    Returns:
        Decorated function that receives overridden resource identifiers when applicable

    Note:
        Must be applied BEFORE the @traced decorator to ensure proper execution order.
    """

    def decorator(func: Callable[..., Any]):
        sig = inspect.signature(func)

        def process_args(args, kwargs) -> dict[str, Any]:
            """Process arguments and apply resource overrides if applicable."""
            # convert both args and kwargs to single dict
            bound = sig.bind_partial(*args, **kwargs)
            bound.apply_defaults()
            all_args = dict(bound.arguments)

            # Get overwrites from context variable
            context_overwrites = _resource_overwrites.get()

            if context_overwrites is not None:
                resource_identifier_value = all_args.get(resource_identifier)
                folder_identifier_value = all_args.get(folder_identifier)

                key = f"{resource_type}.{resource_identifier_value}"
                # try to apply folder path, fallback to resource_type.resource_name
                if folder_identifier_value:
                    key = (
                        f"{key}.{folder_identifier_value}"
                        if f"{key}.{folder_identifier_value}" in context_overwrites
                        else key
                    )

                matched_overwrite = context_overwrites.get(key)

                # Apply the matched overwrite
                if matched_overwrite is not None:
                    if resource_identifier in sig.parameters:
                        all_args[resource_identifier] = (
                            matched_overwrite.resource_identifier
                        )
                    if folder_identifier in sig.parameters:
                        all_args[folder_identifier] = (
                            matched_overwrite.folder_identifier
                        )

            return all_args

        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                all_args = process_args(args, kwargs)
                return await func(**all_args)

            return async_wrapper
        else:

            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                all_args = process_args(args, kwargs)
                return func(**all_args)

            return wrapper

    return decorator
