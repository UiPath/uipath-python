import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

MiddlewareFunc = Callable[
    ..., Tuple[bool, Optional[str]]
]  # Returns (should_continue, errorMessage)


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
    def next(
        cls, command: str, *args: Any, **kwargs: Any
    ) -> Tuple[bool, Optional[str]]:
        """Invoke middleware.

        Returns:
            Tuple[bool, Optional[str]]: (should_continue, errorMessage)
                - continue: True if we want to apply the next middleware, False breaks
                - message: Optional message from the handler
        """
        middlewares = cls.get(command)
        for middleware in middlewares:
            try:
                should_continue, errorMessage = middleware(*args, **kwargs)
                if not should_continue:
                    logger.debug(
                        f"Command '{command}' stopped by {middleware.__name__}"
                    )
                    return False, errorMessage
            except Exception as e:
                logger.error(f"Middleware {middleware.__name__} failed: {str(e)}")
                raise
        return True, None

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
