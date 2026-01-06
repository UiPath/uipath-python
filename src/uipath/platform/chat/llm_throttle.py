"""LLM request throttling utilities.

This module provides concurrency control for LLM API requests to prevent
overwhelming the system with simultaneous calls.
"""

import asyncio

DEFAULT_LLM_CONCURRENCY = 20
_llm_concurrency_limit: int = DEFAULT_LLM_CONCURRENCY
_llm_semaphore: asyncio.Semaphore | None = None
_llm_semaphore_loop: asyncio.AbstractEventLoop | None = None


def get_llm_semaphore() -> asyncio.Semaphore:
    """Get the LLM semaphore, creating with configured limit if not set.

    The semaphore is recreated if called from a different event loop than
    the one it was originally created in. This prevents "bound to a different
    event loop" errors when using multiple asyncio.run() calls.
    """
    global _llm_semaphore, _llm_semaphore_loop

    loop = asyncio.get_running_loop()

    # Recreate semaphore if it doesn't exist or if the event loop changed
    if _llm_semaphore is None or _llm_semaphore_loop is not loop:
        _llm_semaphore = asyncio.Semaphore(_llm_concurrency_limit)
        _llm_semaphore_loop = loop

    return _llm_semaphore


def set_llm_concurrency(limit: int) -> None:
    """Set the max concurrent LLM requests. Call before making any LLM calls.

    Args:
        limit: Maximum number of concurrent LLM requests allowed (must be > 0).

    Raises:
        ValueError: If limit is less than 1.
    """
    if limit < 1:
        raise ValueError("LLM concurrency limit must be at least 1")

    global _llm_concurrency_limit, _llm_semaphore, _llm_semaphore_loop
    _llm_concurrency_limit = limit
    _llm_semaphore = None
    _llm_semaphore_loop = None
