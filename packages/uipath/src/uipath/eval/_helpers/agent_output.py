"""Render a workload's final output for the trajectory judge prompts."""

import json
from typing import Any

from pydantic import TypeAdapter, ValidationError

from uipath.core.chat import (
    UiPathConversationContentPartData,
    UiPathConversationMessageData,
    UiPathExternalValue,
)

AGENT_RESPONSE_MESSAGES_KEY = "uipath__agent_response_messages"
FINAL_RESPONSE_HEADER = "Agent Final Response:"

_messages_adapter = TypeAdapter(list[UiPathConversationMessageData])


def render_agent_output(output: Any) -> str:
    if isinstance(output, str):
        return output
    if isinstance(output, dict) and AGENT_RESPONSE_MESSAGES_KEY in output:
        rendered = _render_conversational_output(output)
        if rendered:
            return rendered
    return _to_json(output)


def append_agent_output(history: str, output: Any) -> str:
    if output is None:
        return history
    section = f"{FINAL_RESPONSE_HEADER}\n{render_agent_output(output)}"
    return f"{history}\n\n{section}" if history else section


def _render_conversational_output(output: dict[str, Any]) -> str:
    try:
        messages = _messages_adapter.validate_python(
            output[AGENT_RESPONSE_MESSAGES_KEY]
        )
    except ValidationError:
        return ""

    # toolCalls are skipped: trace_to_str already renders the executed calls from spans.
    lines = [
        f"[{message.role}] {rendered}"
        for message in messages
        for part in message.content_parts
        if (rendered := _render_content_part(part))
    ]

    structured_fields = {
        k: v for k, v in output.items() if k != AGENT_RESPONSE_MESSAGES_KEY
    }
    if structured_fields:
        lines.append(_to_json(structured_fields))
    return "\n".join(lines)


def _render_content_part(part: UiPathConversationContentPartData) -> str:
    if isinstance(part.data, UiPathExternalValue):
        return f"Attachment ({part.mime_type}): {part.data.uri}"
    inline = part.data.inline
    if inline is None or inline == "":
        return ""
    return inline if isinstance(inline, str) else _to_json(inline)


def _to_json(value: Any) -> str:
    return json.dumps(value, indent=2, default=str)
