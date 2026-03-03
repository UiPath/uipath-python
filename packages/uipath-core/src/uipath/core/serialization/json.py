"""JSON serialization utilities for converting Python objects to JSON formats."""

import json
import uuid
from dataclasses import asdict, is_dataclass
from datetime import date, datetime, time, timezone
from enum import Enum
from typing import Any, cast
from zoneinfo import ZoneInfo

from pydantic import BaseModel


def serialize_defaults(
    obj: Any,
) -> dict[str, Any] | list[Any] | str | int | float | bool | None:
    """Convert Python objects to JSON-serializable formats.

    Handles common Python types that are not natively JSON-serializable:
    - Pydantic models (v1 and v2)
    - Dataclasses
    - Enums
    - Datetime objects
    - Timezone objects
    - Named tuples
    - Sets and tuples

    This function is designed to be used as the `default` parameter in json.dumps():
    ```python
    import json
    result = json.dumps(obj, default=serialize_defaults)
    ```

    Or use the convenience function `serialize_json()` which wraps this:
    ```python
    result = serialize_json(obj)
    ```

    Args:
        obj: The object to serialize

    Returns:
        A JSON-serializable representation of the object:
        - Pydantic models: dict from model_dump()
        - Dataclasses: dict from asdict()
        - Enums: the enum value (recursively serialized)
        - datetime: ISO format string
        - timezone/ZoneInfo: timezone name
        - sets/tuples: converted to lists
        - named tuples: converted to dict
        - Primitives (None, bool, int, float, str, list, dict): returned unchanged
        - Other types: converted to string with str()

    Examples:
        >>> from datetime import datetime
        >>> from pydantic import BaseModel
        >>>
        >>> class User(BaseModel):
        ...     name: str
        ...     created_at: datetime
        >>>
        >>> user = User(name="Alice", created_at=datetime.now())
        >>> import json
        >>> json.dumps(user, default=serialize_defaults)
        '{"name": "Alice", "created_at": "2024-01-01T12:00:00"}'
        >>> # Or use the convenience function
        >>> serialize_json(user)
        '{"name": "Alice", "created_at": "2024-01-01T12:00:00"}'
    """
    # Handle Pydantic BaseModel instances
    if hasattr(obj, "model_dump") and not isinstance(obj, type):
        return obj.model_dump(exclude_none=True, mode="json")

    # Handle Pydantic model classes - convert to schema representation
    if isinstance(obj, type) and issubclass(obj, BaseModel):
        return {
            "__class__": obj.__name__,
            "__module__": obj.__module__,
            "schema": obj.model_json_schema(),
        }

    # Handle Pydantic v1 models
    if hasattr(obj, "dict") and not isinstance(obj, type):
        return obj.dict()

    # Handle objects with to_dict method
    if hasattr(obj, "to_dict") and not isinstance(obj, type):
        return obj.to_dict()

    # Handle objects with as_dict property (UiPathBaseRuntimeError)
    if hasattr(obj, "as_dict") and not isinstance(obj, type):
        return obj.as_dict

    # Handle dataclasses
    if is_dataclass(obj) and not isinstance(obj, type):
        return asdict(obj)

    # Handle enums - recursively serialize the value
    if isinstance(obj, Enum):
        return serialize_defaults(obj.value)

    # Handle sets and tuples
    if isinstance(obj, (set, tuple)):
        # Check if it's a named tuple (has _asdict method)
        if hasattr(obj, "_asdict") and callable(
            obj._asdict  # pyright: ignore[reportAttributeAccessIssue]
        ):
            return cast(
                dict[str, Any],
                obj._asdict(),  # pyright: ignore[reportAttributeAccessIssue]
            )
        # Convert to list
        return list(obj)

    # Handle exceptions
    if isinstance(obj, Exception):
        return str(obj)

    # Handle datetime objects
    if isinstance(obj, datetime):
        return obj.isoformat()

    # Handle timezone objects
    if isinstance(obj, (timezone, ZoneInfo)):
        return obj.tzname(None)

    # Allow JSON-serializable primitives to pass through unchanged
    if obj is None or isinstance(obj, (bool, int, float, str, list, dict)):
        return obj

    # Fallback: convert to string
    return str(obj)


def serialize_json(obj: Any) -> str:
    """Serialize Python object to JSON string.

    This is a convenience function that wraps json.dumps() with serialize_defaults()
    as the default handler for non-JSON-serializable types.

    Args:
        obj: The object to serialize to JSON

    Returns:
        JSON string representation of the object

    Examples:
        >>> from datetime import datetime
        >>> from pydantic import BaseModel
        >>>
        >>> class Task(BaseModel):
        ...     name: str
        ...     created: datetime
        >>>
        >>> task = Task(name="Review PR", created=datetime(2024, 1, 15, 10, 30))
        >>> serialize_json(task)
        '{"name": "Review PR", "created": "2024-01-15T10:30:00"}'
    """
    return json.dumps(obj, default=serialize_defaults)


def serialize_object(obj):
    """Recursively serializes an object and all its nested components."""
    # Handle Pydantic models
    if hasattr(obj, "model_dump"):
        return serialize_object(obj.model_dump(by_alias=True))
    elif hasattr(obj, "dict"):
        return serialize_object(obj.dict())
    elif hasattr(obj, "to_dict"):
        return serialize_object(obj.to_dict())
    # Special handling for UiPathBaseRuntimeErrors
    elif hasattr(obj, "as_dict"):
        return serialize_object(obj.as_dict)
    elif isinstance(obj, (datetime, date, time)):
        return obj.isoformat()
    # Handle dictionaries
    elif isinstance(obj, dict):
        return {k: serialize_object(v) for k, v in obj.items()}
    # Handle lists
    elif isinstance(obj, list):
        return [serialize_object(item) for item in obj]
    # Handle exceptions
    elif isinstance(obj, Exception):
        return str(obj)
    # Handle other iterable objects (convert to dict first)
    elif hasattr(obj, "__iter__") and not isinstance(obj, (str, bytes)):
        try:
            return serialize_object(dict(obj))
        except (TypeError, ValueError):
            return obj
    # UUIDs must be serialized explicitly
    elif isinstance(obj, uuid.UUID):
        return str(obj)
    # Return primitive types as is
    else:
        return obj
