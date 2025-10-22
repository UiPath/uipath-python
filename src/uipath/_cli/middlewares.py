import importlib.metadata
import inspect
import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from ._runtime._contracts import UiPathBaseRuntime, UiPathRuntimeFactory
from ._runtime._runtime_factory import UiPathScriptRuntimeFactory
from ._utils._console import ConsoleLogger

logger = logging.getLogger(__name__)
console = ConsoleLogger()


@dataclass
class MiddlewareResult:
    should_continue: bool
    info_message: Optional[str] = None
    error_message: Optional[str] = None
    should_include_stacktrace: bool = False


MiddlewareFunc = Callable[..., MiddlewareResult]


class Middlewares:
    _middlewares: Dict[str, List[MiddlewareFunc]] = {
        "new": [],
        "init": [],
        "pack": [],
        "publish": [],
        "run": [],
        "dev": [],
        "invoke": [],
        "eval": [],
        "debug": [],
    }
    _runtime_factories: List[UiPathRuntimeFactory[Any, Any]] = []
    _plugins_loaded = False

    @classmethod
    def register(cls, command: str, middleware: MiddlewareFunc) -> None:
        """Register a middleware for a specific command."""
        if command not in cls._middlewares:
            cls._middlewares[command] = []
        cls._middlewares[command].append(middleware)
        logger.debug(
            f"Registered middleware for command '{command}': {middleware.__name__}"
        )

    @classmethod
    def register_runtime_factory(cls, factory: UiPathRuntimeFactory[Any, Any]) -> None:
        """Register a runtime factory in the chain."""
        cls._runtime_factories.append(factory)
        logger.debug(f"Registered runtime factory: {factory.__class__.__name__}")

    @classmethod
    def discover_all_runtimes(cls) -> List[UiPathBaseRuntime]:
        """Discover all runtimes in the current directory using registered runtime factories."""
        if not cls._plugins_loaded:
            cls.load_plugins()

        for factory in cls._runtime_factories:
            try:
                runtimes = factory.discover_all_runtimes()
                if runtimes:
                    return runtimes
            except Exception as e:
                logger.error(
                    f"Runtime factory {factory.__class__.__name__} discovery failed: {e}"
                )
                raise

        return []

    @classmethod
    def get_runtime(cls, entrypoint: str) -> Optional[UiPathBaseRuntime]:
        """Get runtime for a specific entrypoint."""
        if not cls._plugins_loaded:
            cls.load_plugins()

        for factory in cls._runtime_factories:
            try:
                runtime = factory.get_runtime(entrypoint)
                if runtime:
                    return runtime
            except Exception as e:
                logger.error(
                    f"Runtime factory {factory.__class__.__name__} failed for {entrypoint}: {e}"
                )
                raise

        return None

    @classmethod
    def get(cls, command: str) -> List[MiddlewareFunc]:
        """Get all middlewares for a specific command."""
        return cls._middlewares.get(command, [])

    @classmethod
    def next(cls, command: str, *args: Any, **kwargs: Any) -> MiddlewareResult:
        """Invoke middleware."""
        if not cls._plugins_loaded:
            cls.load_plugins()

        middlewares = cls.get(command)
        for middleware in middlewares:
            sig = inspect.signature(middleware)

            # handle older versions of plugins that don't support the new signature
            try:
                bound = sig.bind(*args, **kwargs)
                new_args = bound.args
                new_kwargs = bound.kwargs
            except TypeError:
                console.warning("Install the latest version for uipath packages")
                accepted_args = [
                    name
                    for name, param in sig.parameters.items()
                    if param.kind
                    in (param.POSITIONAL_ONLY, param.POSITIONAL_OR_KEYWORD)
                ]

                trimmed_args = args[: len(accepted_args)]
                trimmed_kwargs = {k: v for k, v in kwargs.items() if k in accepted_args}

                new_args = trimmed_args
                new_kwargs = trimmed_kwargs

            try:
                result = middleware(*new_args, **new_kwargs)
                if not result.should_continue:
                    logger.debug(
                        f"Command '{command}' stopped by {middleware.__name__}"
                    )
                    return result
            except Exception as e:
                logger.error(f"Middleware {middleware.__name__} failed: {str(e)}")
                raise
        return MiddlewareResult(should_continue=True)

    @classmethod
    def clear(cls, command: Optional[str] = None) -> None:
        """Clear middlewares for a specific command or all middlewares if command is None."""
        if command:
            if command in cls._middlewares:
                cls._middlewares[command] = []
        else:
            for cmd in cls._middlewares:
                cls._middlewares[cmd] = []

    @classmethod
    def load_plugins(cls) -> None:
        """Load all plugins and register runtime factories."""
        if cls._plugins_loaded:
            return

        try:
            try:
                entry_points = importlib.metadata.entry_points()
                if hasattr(entry_points, "select"):
                    middlewares = list(entry_points.select(group="uipath.middlewares"))
                else:
                    middlewares = list(entry_points.get("uipath.middlewares", []))
            except Exception:
                middlewares = list(importlib.metadata.entry_points())  # type: ignore
                middlewares = [
                    ep for ep in middlewares if ep.group == "uipath.middlewares"
                ]

            if middlewares:
                logger.debug(f"Found {len(middlewares)} middleware plugins")

                for entry_point in middlewares:
                    try:
                        register_func = entry_point.load()
                        register_func()
                        logger.debug(f"Loaded middleware plugin: {entry_point.name}")
                    except Exception as e:
                        console.error(
                            f"Failed to load middleware plugin {entry_point.name}: {str(e)}",
                            include_traceback=True,
                        )
            else:
                logger.debug("No middleware plugins found")

            # Register the default runtime factory after all the plugin ones
            cls.register_runtime_factory(UiPathScriptRuntimeFactory())
        except Exception as e:
            logger.error(f"No middleware plugins loaded: {str(e)}")
        finally:
            cls._plugins_loaded = True
