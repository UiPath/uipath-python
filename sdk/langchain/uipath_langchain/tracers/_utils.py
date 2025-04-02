import datetime
from zoneinfo import ZoneInfo


def _simple_serialize_defaults(obj):
    if hasattr(obj, "model_dump"):
        return obj.model_dump(exclude_none=True, mode="json")
    if hasattr(obj, "dict"):
        return obj.dict()
    if hasattr(obj, "to_dict"):
        return obj.to_dict()

    if isinstance(obj, (set, tuple)):
        if hasattr(obj, "_asdict") and callable(obj._asdict):
            return obj._asdict()
        return list(obj)

    if isinstance(obj, datetime.datetime):
        return obj.isoformat()

    if isinstance(obj, (datetime.timezone, ZoneInfo)):
        return obj.tzname(None)

    return str(obj)
