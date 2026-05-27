"""Tests for `UiPathConversationMessage` input validation.

Conversational Agent Service contract treats `role` + `contentParts` as
the load-bearing fields for an inbound user message. `messageId` and
`contentPartId` are GUIDs that identify entities in the conversation
hierarchy; when omitted on input, the model fills them with fresh
UUIDs (matching what `uipath dev` does server-side). `createdAt`,
`updatedAt`, `spanId`, and `toolCalls` are server-allocated and absent
from client input.

These tests pin that behavior so `--input-file` payloads from
`uip codedagent run` validate against the model without requiring
callers to hand-generate UUIDs.
"""

from __future__ import annotations

from uipath.core.chat import UiPathConversationMessage


def test_minimal_user_message_validates_and_fills_ids() -> None:
    msg = UiPathConversationMessage.model_validate(
        {
            "role": "user",
            "contentParts": [
                {
                    "mimeType": "text/plain",
                    "data": {"inline": "hello world"},
                }
            ],
        }
    )
    assert msg.role == "user"
    assert msg.tool_calls == []
    assert msg.created_at is None
    assert msg.updated_at is None
    assert msg.message_id  # auto-generated UUID
    assert msg.content_parts[0].content_part_id  # auto-generated UUID
    assert msg.content_parts[0].citations == []


def test_explicit_ids_are_preserved() -> None:
    msg = UiPathConversationMessage.model_validate(
        {
            "messageId": "00000000-0000-0000-0000-000000000001",
            "role": "user",
            "contentParts": [
                {
                    "contentPartId": "00000000-0000-0000-0000-000000000002",
                    "mimeType": "text/plain",
                    "data": {"inline": "hello world"},
                }
            ],
        }
    )
    assert msg.message_id == "00000000-0000-0000-0000-000000000001"
    assert (
        msg.content_parts[0].content_part_id == "00000000-0000-0000-0000-000000000002"
    )
