from typing import Any


class SingletonMeta(type):
    _instances: dict[type, type] = {}

    def __call__(cls, *args: tuple[Any, ...], **kwargs: dict[str, Any]) -> type:
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]


# TODO: add utils for retry
