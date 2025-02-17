import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class MiddlewareResult:
    should_continue: bool
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

    @classmethod
    def register(cls, command: str, middleware: MiddlewareFunc) -> None:
        """Register a middleware for a specific command"""
        if command not in cls._middlewares:
            cls._middlewares[command] = []
        cls._middlewares[command].append(middleware)
        logger.debug(
            f"Registered middleware for command '{command}': {middleware.__name__}"
        )

    @classmethod
    def get(cls, command: str) -> List[MiddlewareFunc]:
        """Get all middlewares for a specific command"""
        return cls._middlewares.get(command, [])

    @classmethod
    def next(cls, command: str, *args: Any, **kwargs: Any) -> MiddlewareResult:
        """Invoke middleware.

        Returns:
            MiddlewareResult containing:
                - should_continue: True if we want to apply the next middleware, False breaks
                - error_message: Optional message from the handler
                - should_include_stacktrace: Whether to include stacktrace in error output
        """
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
        """Clear middlewares for a specific command or all middlewares if command is None.
        Useful for testing."""
        if command:
            if command in cls._middlewares:
                cls._middlewares[command] = []
        else:
            for cmd in cls._middlewares:
                cls._middlewares[cmd] = []
