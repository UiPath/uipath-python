"""Utility functions for evaluation progress reporting.

This module contains decorators and helper functions used by the
progress reporter and related components.
"""

import functools
import logging

logger = logging.getLogger(__name__)


def gracefully_handle_errors(func):
    """Decorator to catch and log errors without stopping execution.

    This decorator wraps async functions and catches any exceptions,
    logging them as warnings instead of allowing them to propagate.
    This ensures that progress reporting failures don't break the
    main evaluation flow.

    Args:
        func: The async function to wrap

    Returns:
        The wrapped function that catches and logs errors
    """

    @functools.wraps(func)
    async def wrapper(self, *args, **kwargs):
        try:
            return await func(self, *args, **kwargs)
        except Exception as e:
            if hasattr(self, "_console"):
                error_type = type(e).__name__
                logger.debug(f"Full error details: {e}")
                logger.warning(
                    f"Cannot report progress to SW. "
                    f"Function: {func.__name__}, "
                    f"Error type: {error_type}, "
                    f"Details: {e}"
                )
            return None

    return wrapper
