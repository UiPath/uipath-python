import functools
import inspect
from typing import Any, Callable, TypeVar

from ._read_overwrites import read_resource_overwrites

T = TypeVar("T")


def infer_bindings(
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

            if name in all_args or folder_path in all_args:
                with read_resource_overwrites(
                    resource_type,
                    all_args.get(name),  # type: ignore
                    all_args.get(folder_path, None),
                ) as (name_overwrite_or_default, folder_path_overwrite_or_default):
                    all_args[name] = name_overwrite_or_default
                    all_args[folder_path] = folder_path_overwrite_or_default

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
