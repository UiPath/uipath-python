"""Body keys given as paths, expanded into the nested body a connector expects."""

import re
from typing import Any, Dict, List

_INDEXED_SEGMENT_RE = re.compile(r"^(.*?)\[(\d+)]$")
_WILDCARD_SUFFIX = "[*]"


def _is_path_key(key: str) -> bool:
    return "." in key or "[" in key


def expand_body_paths(body: Dict[str, Any]) -> Dict[str, Any]:
    """Build the nested body a connector expects from a body whose keys are paths.

    `{"fields.summary": "x"}` becomes `{"fields": {"summary": "x"}}`. A segment
    can address an array item (`items[2].name`) or every item of an array
    (`items[*].name`). Keys without a path are copied as they are, and nested
    values are never rewritten. A body with no path key is returned untouched.
    """
    if not any(isinstance(key, str) and _is_path_key(key) for key in body):
        return body

    output: Dict[str, Any] = {}
    for key, value in body.items():
        if isinstance(key, str) and _is_path_key(key):
            _assign_path(output, key, value)
        else:
            output[key] = value
    return output


def _assign_path(target: Dict[str, Any], path: str, value: Any) -> None:
    segments = path.split(".")
    current = target

    for index, segment in enumerate(segments):
        is_last = index == len(segments) - 1

        indexed = _INDEXED_SEGMENT_RE.match(segment)
        if indexed:
            items = _list_in(current, indexed.group(1))
            position = int(indexed.group(2))
            while len(items) <= position:
                items.append({})
            if is_last:
                items[position] = value
                return
            current = _dict_at(items, position)
            continue

        if segment.endswith(_WILDCARD_SUFFIX):
            key = segment[: -len(_WILDCARD_SUFFIX)]
            _assign_to_every_item(current, key, ".".join(segments[index + 1 :]), value)
            return

        if is_last:
            current[segment] = value
            return
        current = _dict_in(current, segment)


def _list_in(parent: Dict[str, Any], key: str) -> List[Any]:
    existing = parent.get(key)
    if isinstance(existing, list):
        return existing
    created: List[Any] = []
    parent[key] = created
    return created


def _dict_in(parent: Dict[str, Any], key: str) -> Dict[str, Any]:
    existing = parent.get(key)
    if isinstance(existing, dict):
        return existing
    created: Dict[str, Any] = {}
    parent[key] = created
    return created


def _dict_at(items: List[Any], position: int) -> Dict[str, Any]:
    existing = items[position]
    if isinstance(existing, dict):
        return existing
    created: Dict[str, Any] = {}
    items[position] = created
    return created


def _assign_to_every_item(
    parent: Dict[str, Any], key: str, remaining_path: str, value: Any
) -> None:
    # A list value replaces the whole list
    if isinstance(value, list):
        parent[key] = value
        return

    items = _list_in(parent, key)
    if not items:
        items.append({})

    for position in range(len(items)):
        item = _dict_at(items, position)
        if remaining_path:
            _assign_path(item, remaining_path, value)
        elif isinstance(value, dict):
            _merge_into(item, value)


def _merge_into(current: Dict[str, Any], incoming: Dict[str, Any]) -> None:
    for key, value in incoming.items():
        if isinstance(value, dict):
            _merge_into(_dict_in(current, key), value)
        else:
            current[key] = value
