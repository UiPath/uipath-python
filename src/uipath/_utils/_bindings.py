import functools
import inspect
from contextvars import ContextVar, Token
from typing import Any, Callable, Coroutine, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ResourceOverwrite(BaseModel):
    """Represents a resource overwrite configuration.

    Attributes:
        overwrite_name: The name of the resource being overwritten
        overwrite_folder_path: The folder path of the overwrite resource
    """

    model_config = ConfigDict(
        populate_by_name=True,
    )

    overwrite_name: str = Field(alias="name")
    overwrite_folder_path: str = Field(alias="folderPath")


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
    name: str = "name",
    folder_path: str = "folder_path",
    ignore: bool = False,
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
                resource_name = all_args.get(name)
                resource_folder_path = all_args.get(folder_path)

                key = f"{resource_type}.{resource_name}"
                # try to apply folder path, fallback to resource_type.resource_name
                if resource_folder_path:
                    key = (
                        f"{key}.{resource_folder_path}"
                        if f"{key}.{resource_folder_path}" in context_overwrites
                        else key
                    )

                matched_overwrite = context_overwrites.get(key)

                # Apply the matched overwrite
                if matched_overwrite is not None:
                    if name in sig.parameters:
                        all_args[name] = matched_overwrite.overwrite_name
                    if folder_path in sig.parameters:
                        all_args[folder_path] = matched_overwrite.overwrite_folder_path

            return func(**all_args)

        wrapper._should_infer_bindings = not ignore  # type: ignore
        wrapper._infer_bindings_mappings = {"name": name, "folder_path": folder_path}  # type: ignore
        return wrapper

    return decorator


def get_inferred_bindings_names(cls: T):
    inferred_bindings = {}
    for name, method in inspect.getmembers(cls, inspect.isfunction):
        if hasattr(method, "_should_infer_bindings") and method._should_infer_bindings:
            inferred_bindings[name] = method._infer_bindings_mappings  # type: ignore

    return inferred_bindings
