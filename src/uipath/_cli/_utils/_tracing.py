import datetime
import logging
from zoneinfo import ZoneInfo


class IgnoreSpecificUrl(logging.Filter):
    def __init__(self, url_to_ignore):
        super().__init__()
        self.url_to_ignore = url_to_ignore

    def filter(self, record):
        try:
            # Suppress all HTTP Request logs from httpx
            if record.msg == 'HTTP Request: %s %s "%s %d %s"':
                return False

        except Exception:
            return False
        return True


def setup_tracer_httpx_logging(url: str):
    # Create a custom logger for httpx
    # Add the custom filter to the root logger
    logging.getLogger("httpx").addFilter(IgnoreSpecificUrl(url))


def simple_serialize_defaults(obj):
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
