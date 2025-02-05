import time
from functools import wraps
from typing import Callable, ParamSpec, TypeVar

T = TypeVar("T")
P = ParamSpec("P")


def retry(
    times: int, exceptions: tuple[type[BaseException], ...], delay: int = 500
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            attempt = 0
            while attempt < times:
                try:
                    return func(*args, **kwargs)
                except exceptions:
                    attempt += 1
                    time.sleep(delay / 1000)
            return func(*args, **kwargs)

        return wrapper

    return decorator
