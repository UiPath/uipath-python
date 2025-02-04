import importlib.metadata
import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


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
            try:
                result = middleware(*args, **kwargs)
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
                logger.info(f"Found {len(middlewares)} middleware plugins")

                for entry_point in middlewares:
                    try:
                        register_func = entry_point.load()
                        register_func()
                        logger.info(f"Loaded middleware plugin: {entry_point.name}")
                    except Exception as e:
                        logger.error(
                            f"Failed to load middleware plugin {entry_point.name}: {str(e)}",
                            exc_info=True,
                        )
            else:
                logger.info("No middleware plugins found")

        except Exception as e:
            logger.error(f"No middleware plugins loaded: {str(e)}")
        finally:
            cls._plugins_loaded = True
