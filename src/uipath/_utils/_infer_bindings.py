import functools
import inspect
from typing import Any, Callable, TypeVar

T = TypeVar("T")


def infer_bindings(
    name: str = "name", folder_path: str = "folder_path"
) -> Callable[..., Any]:
    def decorator(func: Callable[..., Any]):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        wrapper._should_infer_bindings = True  # type: ignore
        wrapper._infer_bindings_mappings = {"name": name, "folder_path": folder_path}  # type: ignore

        return wrapper

    return decorator


def get_inferred_bindings_names(cls: T):
    inferred_bindings = {}
    for name, method in inspect.getmembers(cls, inspect.isfunction):
        if hasattr(method, "_should_infer_bindings") and method._should_infer_bindings:
            inferred_bindings[name] = method._infer_bindings_mappings  # type: ignore

    return inferred_bindings
