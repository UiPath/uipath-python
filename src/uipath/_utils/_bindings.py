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

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

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
    connection_id: str = Field(alias="connectionId")
    element_instance_id: str = Field(alias="elementInstanceId")
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
    def decorator(func: Callable[..., Any]):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # convert both args and kwargs to single dict
            sig = inspect.signature(func)
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

            return func(**all_args)

        wrapper._should_infer_bindings = True  # type: ignore
        wrapper._infer_bindings_mappings = {  # type: ignore
            "name": resource_identifier,
            "folder_path": folder_identifier,
        }
        return wrapper

    return decorator


def get_inferred_bindings_names(cls: T):
    inferred_bindings = {}
    for name, method in inspect.getmembers(cls, inspect.isfunction):
        if hasattr(method, "_should_infer_bindings") and method._should_infer_bindings:
            inferred_bindings[name] = method._infer_bindings_mappings  # type: ignore

    return inferred_bindings
