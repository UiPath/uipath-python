"""Runtime factory discovery for the CLI.

Commands that execute an agent need ``UiPathRuntimeFactoryRegistry`` populated
with the built-in factory and every ``uipath.runtime.factories`` entry point.
Loading those entry points imports each installed agent stack (langgraph,
llama_index, ...), so it happens inside the command callback, after click has
parsed the arguments. Rendering ``--help`` and shell completion resolve the
command object but never call it, so they never pay for it.
"""

import functools
from collections.abc import Callable
from importlib.metadata import entry_points
from typing import ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")

_initialized = False


def load_runtime_factories() -> None:
    """Auto-discover and register all factory plugins."""
    for ep in entry_points(group="uipath.runtime.factories"):
        try:
            register_func = ep.load()
            register_func()
        except Exception as e:
            print(f"Failed to load factory {ep.name}: {e}")


def ensure_runtime_initialized() -> None:
    """Register the built-in runtime factory and every plugin factory, once."""
    global _initialized
    if _initialized:
        return
    _initialized = True

    from uipath.functions import register_default_runtime_factory

    register_default_runtime_factory()
    load_runtime_factories()


def requires_runtime(func: Callable[P, R]) -> Callable[P, R]:
    """Initialize the runtime factories before a command callback runs.

    Stack it under ``@click.command()``, above ``@track_command`` so the
    factory load stays out of the command's measured duration:

        @click.command()
        @requires_runtime
        @track_command("run")
        def run(...):
            ...

    Args:
        func: The click command callback.

    Returns:
        The callback, wrapped to populate the runtime factory registry first.
    """

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        ensure_runtime_initialized()
        return func(*args, **kwargs)

    return wrapper
