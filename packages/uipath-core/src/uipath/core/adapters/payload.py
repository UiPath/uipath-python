"""Shared payload helpers for governance framework plugins.

The per-framework payload extraction stays in the plugins (each reads its own
SDK types); the capping, serialisation and tool-arg coercion are shared here so
every plugin caps and coerces identically.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from typing import Any, Iterable

logger = logging.getLogger(__name__)

# Character budget for the text scanned per model / tool hook.
MODEL_TEXT_CAP = 64000


def join_within_cap(
    pieces: Iterable[str], sep: str = "\n", *, cap: int = MODEL_TEXT_CAP
) -> str:
    """Join non-empty ``pieces`` with ``sep``, stopping once ``cap`` is reached."""
    collected: list[str] = []
    remaining = cap
    for piece in pieces:
        if remaining <= 0:
            break
        if not piece:
            continue
        collected.append(piece[:remaining])
        remaining -= len(piece) + len(sep)
    return sep.join(collected)[:cap]


def stringify(value: Any, *, cap: int = MODEL_TEXT_CAP) -> str:
    """Render a dict / object payload as compact text, capped at ``cap``.

    Strings pass through; other values are JSON encoded (``default=str``),
    falling back to ``str()`` on a serialisation error (e.g. a circular ref).
    """
    if isinstance(value, str):
        return value[:cap]
    try:
        return json.dumps(value, default=str, ensure_ascii=False)[:cap]
    except (TypeError, ValueError):
        return str(value)[:cap]


def coerce_args(value: Any) -> dict[str, Any]:
    """Normalise tool-call arguments to a dict for the evaluator.

    Handles the shapes plugins see: ``None``, a ``Mapping``, a JSON string, a
    pydantic model (``model_dump``), or anything else. Non-dict payloads are
    preserved rather than dropped, so an arg-based policy can still scan them:
    non-dict JSON under ``_``, malformed JSON under ``_raw``, other values
    under ``_``.
    """
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return {"_raw": value}
        return parsed if isinstance(parsed, dict) else {"_": parsed}
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        try:
            dumped = model_dump()
        except Exception as e:  # noqa: BLE001
            logger.warning(
                "coerce_args: model_dump() failed for %s (%s)",
                type(value).__name__,
                e,
            )
            return {}
        if isinstance(dumped, dict):
            return dumped
    return {"_": value}
