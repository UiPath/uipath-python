"""Legacy backwards compatibility for flat AgentDefinition formats.

Converts legacy flat fields (systemPrompt, userPrompt, tools, contexts,
escalations) into the unified format (messages, resources,
features) before Pydantic validation runs.
"""

from __future__ import annotations

from typing import Any, Dict


def normalize_legacy_format(data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a legacy flat agent definition into the unified format.

    Mutates and returns *data*.  Safe to call on already-modern payloads
    (existing ``messages`` / ``resources`` / ``features`` are never overwritten).
    """
    _normalize_messages(data)
    _normalize_legacy_resources(data)
    _cleanup_legacy_fields(data)
    return data


def _normalize_messages(data: Dict[str, Any]) -> None:
    messages = data.get("messages")
    if messages:
        return

    system_prompt = data.get("systemPrompt")
    user_prompt = data.get("userPrompt")

    if system_prompt is None and user_prompt is None:
        return

    built: list[Dict[str, Any]] = []

    if system_prompt is not None:
        if isinstance(system_prompt, dict):
            built.append({"role": "system", **system_prompt})
        else:
            built.append({"role": "system", "content": str(system_prompt)})

    if user_prompt is not None:
        if isinstance(user_prompt, dict):
            built.append({"role": "user", **user_prompt})
        else:
            built.append({"role": "user", "content": str(user_prompt)})

    data["messages"] = built


def _normalize_legacy_resources(data: Dict[str, Any]) -> None:
    resources = data.get("resources")
    if resources:
        return

    built: list[Dict[str, Any]] = []

    for item in data.get("tools") or []:
        if isinstance(item, dict):
            item.setdefault("$resourceType", "tool")
            item.setdefault("isEnabled", True)
        built.append(item)

    for item in data.get("contexts") or []:
        if isinstance(item, dict):
            item.setdefault("$resourceType", "context")
        built.append(item)

    for item in data.get("escalations") or []:
        if isinstance(item, dict):
            item.setdefault("$resourceType", "escalation")
        built.append(item)

    if built:
        data["resources"] = built


_LEGACY_KEYS = frozenset(
    ["systemPrompt", "userPrompt", "tools", "contexts", "escalations"]
)


def _cleanup_legacy_fields(data: Dict[str, Any]) -> None:
    for key in _LEGACY_KEYS:
        data.pop(key, None)
