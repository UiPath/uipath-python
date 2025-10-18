import importlib.metadata
import inspect
import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

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
        """Load all middlewares registered via entry points."""
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

        except Exception as e:
            logger.error(f"No middleware plugins loaded: {str(e)}")
        finally:
            cls._plugins_loaded = True
