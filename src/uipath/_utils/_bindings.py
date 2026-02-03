from __future__ import annotations

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
    def folder_identifier(self) -> str | None:
        """The folder location identifier for this resource."""
        pass


class SystemResourceOverwrite(ResourceOverwrite):
    resource_type: Literal["index"]
    name: str = Field(alias="name")
    folder_key: str = Field(alias="folderKey")

    @property
    def resource_identifier(self) -> str:
        return self.name

    @property
    def folder_identifier(self) -> str:
        return self.folder_key


class GenericResourceOverwrite(ResourceOverwrite):
    resource_type: Literal["process", "index", "app", "asset", "bucket", "mcpServer"]
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


# this context var holds a dictionary in the following format:
# {"binding_key: applied_overwrite | None"}
# for system resources (e.g. system indexes) we need to make sure that a binding is set with no corresponding overwrite
_binding_overwrites: ContextVar[dict[str, ResourceOverwrite | None] | None] = (
    ContextVar("binding_overwrites", default=None)
)


class ResourceOverwritesContext:
    def __init__(
        self,
        get_overwrites_callable: Callable[
            [], Coroutine[Any, Any, dict[str, ResourceOverwrite | None]]
        ],
    ):
        self.get_overwrites_callable = get_overwrites_callable
        self._token: Token[dict[str, ResourceOverwrite | None] | None] | None = None
        self.overwrites_count = 0

    async def __aenter__(self) -> ResourceOverwritesContext:
        overwrites = await self.get_overwrites_callable()
        self._token = _binding_overwrites.set(overwrites)
        self.overwrites_count = len(overwrites)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._token:
            _binding_overwrites.reset(self._token)


class ArgumentsProcessingResponse(BaseModel):
    arguments: dict[str, Any]
    can_apply_resolution: bool = False


def resource_override(
    resource_type: str,
    resource_identifier: str = "name",
    folder_identifier: str = "folder_path",
    resolution_func_name: str | None = None,
    resolution_coroutine_name: str | None = None,
    resolution_resource_identifier: str = "name",
    resolution_folder_identifier: str = "folder_path",
) -> Callable[..., Any]:
    """Decorator for applying resource overrides for an overridable resource.

    It checks the current ContextVar to identify the requested overrides and, if any key matches, it invokes the decorated function
    with the extracted resource and folder identifiers.

    Args:
        resource_type: Type of resource to check for overrides (e.g., "asset", "bucket")
        resource_identifier: Key name for the resource ID in override data (default: "name")
        folder_identifier: Key name for the folder path in override data (default: "folder_path")
        resolution_func_name: Optional sync callable for resolving the overwrite when binding is set but overwrite not present.
        resolution_coroutine_name: Optional async callable for resolving the overwrite when binding is set but overwrite not present.
                                    Note: those are passed string reference since decorators are evaluated at class definition time.
        resolution_resource_identifier: Key name for the resource ID in resolution data (default: "name")
        resolution_folder_identifier: Key name for the folder identifier in resolution data (default: "folder_path")

    Returns:
        Decorated function that receives overridden resource identifiers when applicable

    Note:
        Must be applied BEFORE the @traced decorator to ensure proper execution order.
    """

    def decorator(func: Callable[..., Any]):
        sig = inspect.signature(func)

        def apply_overwrite(
            all_args: dict[str, Any],
            matched_overwrite: ResourceOverwrite,
            is_resolution_overwrite=False,
        ) -> None:
            resource_id = (
                resolution_resource_identifier
                if is_resolution_overwrite
                else resource_identifier
            )
            folder_id = (
                resolution_folder_identifier
                if is_resolution_overwrite
                else folder_identifier
            )

            if resource_id in sig.parameters:
                all_args[resource_id] = matched_overwrite.resource_identifier
            if folder_id in sig.parameters:
                all_args[folder_id] = matched_overwrite.folder_identifier

        def process_args(args, kwargs) -> ArgumentsProcessingResponse:
            """Process arguments and apply resource overrides if applicable."""
            # convert both args and kwargs to single dict
            bound = sig.bind_partial(*args, **kwargs)
            bound.apply_defaults()
            all_args = dict(bound.arguments)

            if (
                "kwargs" in sig.parameters
                and sig.parameters["kwargs"].kind == inspect.Parameter.VAR_KEYWORD
            ):
                extra_kwargs = all_args.pop("kwargs", {})
                all_args.update(extra_kwargs)

            # Get overwrites from context variable

            context_overwrites = _binding_overwrites.get()

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

                try:
                    matched_overwrite = context_overwrites[key]
                except KeyError:
                    # binding not set, default to original parameters
                    return ArgumentsProcessingResponse(arguments=all_args)

                # Apply the matched overwrite
                if matched_overwrite is not None:
                    apply_overwrite(all_args, matched_overwrite)
                    return ArgumentsProcessingResponse(arguments=all_args)

                # binding is set but no corresponding overwrite exists
                # we can try to apply the resolution
                return ArgumentsProcessingResponse(
                    arguments=all_args, can_apply_resolution=True
                )

            return ArgumentsProcessingResponse(arguments=all_args)

        def filter_function_args(func: Callable[..., Any], all_args: dict[str, Any]):
            callable_sig = inspect.signature(func)
            filtered_args = {}
            for param_name in callable_sig.parameters:
                if param_name != "self" and param_name in all_args:
                    filtered_args[param_name] = all_args[param_name]
            return filtered_args

        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                process_args_response = process_args(args, kwargs)
                all_args = process_args_response.arguments
                if not (
                    process_args_response.can_apply_resolution
                    and resolution_coroutine_name
                ):
                    return await func(**all_args)

                # apply resolution coroutine
                invoked_class_instance = args[0]  # self
                resolution_coroutine: (
                    Callable[..., Coroutine[Any, Any, ResourceOverwrite | None]] | None
                ) = getattr(invoked_class_instance, resolution_coroutine_name)
                if resolution_coroutine and (
                    resource_overwrite := await resolution_coroutine(
                        **filter_function_args(
                            resolution_coroutine, process_args_response.arguments
                        )
                    )
                ):
                    apply_overwrite(
                        all_args, resource_overwrite, is_resolution_overwrite=True
                    )
                return await func(**all_args)

            return async_wrapper

        else:

            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                process_args_response = process_args(args, kwargs)
                all_args = process_args_response.arguments
                if not (
                    process_args_response.can_apply_resolution and resolution_func_name
                ):
                    return func(**all_args)

                # apply resolution function
                invoked_class_instance = args[0]  # self
                resolution_func: Callable[..., ResourceOverwrite | None] | None = (
                    getattr(invoked_class_instance, resolution_func_name)
                )
                if resolution_func and (
                    resource_overwrite := resolution_func(
                        **filter_function_args(
                            resolution_func, process_args_response.arguments
                        )
                    )
                ):
                    apply_overwrite(
                        all_args, resource_overwrite, is_resolution_overwrite=True
                    )
                return func(**all_args)

            return wrapper

    return decorator
