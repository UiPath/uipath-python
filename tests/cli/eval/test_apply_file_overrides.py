"""Tests for _apply_file_overrides_to_conversational_inputs in uipath.eval.helpers."""

from typing import Any

from uipath._cli._evals._conversational_utils import (
    LegacyConversationalEvalInput,
    LegacyConversationalEvalInputAgentMessage,
    LegacyConversationalEvalJobAttachmentReference,
    LegacyConversationalEvalUserMessage,
)
from uipath.eval.helpers import _apply_file_overrides_to_conversational_inputs


def _make_attachment(
    id: str, full_name: str, mime_type: str = "application/pdf"
) -> LegacyConversationalEvalJobAttachmentReference:
    return LegacyConversationalEvalJobAttachmentReference(
        ID=id, FullName=full_name, MimeType=mime_type
    )


def _make_conversational_inputs(
    current_prompt_text: str = "hello",
    current_prompt_attachments: list[LegacyConversationalEvalJobAttachmentReference]
    | None = None,
    conversation_history: list[list[Any]] | None = None,
) -> LegacyConversationalEvalInput:
    current_user_prompt = LegacyConversationalEvalUserMessage(
        role="user",
        text=current_prompt_text,
        attachments=current_prompt_attachments,
    )
    return LegacyConversationalEvalInput(
        conversationHistory=conversation_history or [],
        currentUserPrompt=current_user_prompt,
    )


class TestApplyFileOverridesNoOp:
    """Tests where the function should be a no-op."""

    def test_empty_overrides(self) -> None:
        attachment = _make_attachment("old-id", "file.pdf")
        inputs = _make_conversational_inputs(current_prompt_attachments=[attachment])
        _apply_file_overrides_to_conversational_inputs(inputs, {})
        assert attachment.id == "old-id"

    def test_no_overrides(self) -> None:
        attachment = _make_attachment("old-id", "file.pdf")
        inputs = _make_conversational_inputs(current_prompt_attachments=[attachment])
        _apply_file_overrides_to_conversational_inputs(inputs, {})
        assert attachment.id == "old-id"

    def test_overrides_without_id_key_are_ignored(self) -> None:
        """Dicts without 'ID' key should not be treated as file overrides."""
        attachment = _make_attachment("old-id", "file.pdf")
        inputs = _make_conversational_inputs(current_prompt_attachments=[attachment])
        overrides = {"someField": {"name": "not-a-file"}}
        _apply_file_overrides_to_conversational_inputs(inputs, overrides)
        assert attachment.id == "old-id"

    def test_string_override_values_are_ignored(self) -> None:
        """Non-dict, non-list override values should be skipped."""
        attachment = _make_attachment("old-id", "file.pdf")
        inputs = _make_conversational_inputs(current_prompt_attachments=[attachment])
        overrides = {"someField": "just a string", "anotherField": 42}
        _apply_file_overrides_to_conversational_inputs(inputs, overrides)
        assert attachment.id == "old-id"

    def test_no_matching_attachment_by_name(self) -> None:
        """Override with a FullName that doesn't match any attachment."""
        attachment = _make_attachment("old-id", "file.pdf")
        inputs = _make_conversational_inputs(current_prompt_attachments=[attachment])
        overrides = {
            "files": {
                "ID": "new-id",
                "FullName": "other.pdf",
                "MimeType": "application/pdf",
            }
        }
        _apply_file_overrides_to_conversational_inputs(inputs, overrides)
        assert attachment.id == "old-id"

    def test_no_attachments_on_current_prompt(self) -> None:
        """No error when current_user_prompt has no attachments."""
        inputs = _make_conversational_inputs(current_prompt_attachments=None)
        overrides = {
            "files": {
                "ID": "new-id",
                "FullName": "file.pdf",
                "MimeType": "application/pdf",
            }
        }
        _apply_file_overrides_to_conversational_inputs(inputs, overrides)

    def test_empty_attachments_list(self) -> None:
        """No error when current_user_prompt has empty attachments list."""
        inputs = _make_conversational_inputs(current_prompt_attachments=[])
        overrides = {
            "files": {
                "ID": "new-id",
                "FullName": "file.pdf",
                "MimeType": "application/pdf",
            }
        }
        _apply_file_overrides_to_conversational_inputs(inputs, overrides)


class TestApplyFileOverridesSingleDict:
    """Tests for single-dict override values."""

    def test_override_updates_id(self) -> None:
        attachment = _make_attachment("old-id", "report.pdf")
        inputs = _make_conversational_inputs(current_prompt_attachments=[attachment])
        overrides = {
            "files": {
                "ID": "new-id",
                "FullName": "report.pdf",
                "MimeType": "application/pdf",
            }
        }
        _apply_file_overrides_to_conversational_inputs(inputs, overrides)
        assert attachment.id == "new-id"

    def test_override_updates_full_name(self) -> None:
        attachment = _make_attachment("old-id", "report.pdf")
        inputs = _make_conversational_inputs(current_prompt_attachments=[attachment])
        overrides = {
            "files": {
                "ID": "new-id",
                "FullName": "report.pdf",
                "MimeType": "text/plain",
            }
        }
        _apply_file_overrides_to_conversational_inputs(inputs, overrides)
        assert attachment.full_name == "report.pdf"

    def test_override_updates_mime_type(self) -> None:
        attachment = _make_attachment("old-id", "report.pdf", "application/pdf")
        inputs = _make_conversational_inputs(current_prompt_attachments=[attachment])
        overrides = {
            "files": {
                "ID": "new-id",
                "FullName": "report.pdf",
                "MimeType": "text/plain",
            }
        }
        _apply_file_overrides_to_conversational_inputs(inputs, overrides)
        assert attachment.mime_type == "text/plain"

    def test_override_without_mime_type_preserves_original(self) -> None:
        attachment = _make_attachment("old-id", "report.pdf", "application/pdf")
        inputs = _make_conversational_inputs(current_prompt_attachments=[attachment])
        overrides = {"files": {"ID": "new-id", "FullName": "report.pdf"}}
        _apply_file_overrides_to_conversational_inputs(inputs, overrides)
        assert attachment.id == "new-id"
        assert attachment.mime_type == "application/pdf"


class TestApplyFileOverridesArrayValues:
    """Tests for array-based override values."""

    def test_override_from_array_of_files(self) -> None:
        attachment = _make_attachment("old-id", "doc.pdf")
        inputs = _make_conversational_inputs(current_prompt_attachments=[attachment])
        overrides = {
            "files": [
                {
                    "ID": "new-id-1",
                    "FullName": "doc.pdf",
                    "MimeType": "application/pdf",
                },
                {
                    "ID": "new-id-2",
                    "FullName": "other.pdf",
                    "MimeType": "application/pdf",
                },
            ]
        }
        _apply_file_overrides_to_conversational_inputs(inputs, overrides)
        assert attachment.id == "new-id-1"

    def test_multiple_attachments_matched_from_array(self) -> None:
        att1 = _make_attachment("old-1", "a.pdf")
        att2 = _make_attachment("old-2", "b.pdf")
        inputs = _make_conversational_inputs(current_prompt_attachments=[att1, att2])
        overrides = {
            "files": [
                {"ID": "new-1", "FullName": "a.pdf", "MimeType": "application/pdf"},
                {"ID": "new-2", "FullName": "b.pdf", "MimeType": "text/plain"},
            ]
        }
        _apply_file_overrides_to_conversational_inputs(inputs, overrides)
        assert att1.id == "new-1"
        assert att2.id == "new-2"
        assert att2.mime_type == "text/plain"

    def test_non_dict_items_in_array_are_skipped(self) -> None:
        """Non-dict items in an override array should be safely ignored."""
        attachment = _make_attachment("old-id", "doc.pdf")
        inputs = _make_conversational_inputs(current_prompt_attachments=[attachment])
        overrides = {
            "files": [
                "not-a-dict",
                42,
                {"ID": "new-id", "FullName": "doc.pdf", "MimeType": "application/pdf"},
            ]
        }
        _apply_file_overrides_to_conversational_inputs(inputs, overrides)
        assert attachment.id == "new-id"

    def test_dicts_without_id_in_array_are_skipped(self) -> None:
        """Dicts in array that lack 'ID' should not be treated as file overrides."""
        attachment = _make_attachment("old-id", "doc.pdf")
        inputs = _make_conversational_inputs(current_prompt_attachments=[attachment])
        overrides = {
            "files": [
                {"name": "not-a-file"},
                {"ID": "new-id", "FullName": "doc.pdf", "MimeType": "application/pdf"},
            ]
        }
        _apply_file_overrides_to_conversational_inputs(inputs, overrides)
        assert attachment.id == "new-id"


class TestApplyFileOverridesMultipleOverrideKeys:
    """Tests for overrides with multiple top-level keys."""

    def test_file_overrides_collected_across_multiple_keys(self) -> None:
        att1 = _make_attachment("old-1", "a.pdf")
        att2 = _make_attachment("old-2", "b.pdf")
        inputs = _make_conversational_inputs(current_prompt_attachments=[att1, att2])
        overrides = {
            "primaryFile": {
                "ID": "new-1",
                "FullName": "a.pdf",
                "MimeType": "application/pdf",
            },
            "secondaryFiles": [
                {"ID": "new-2", "FullName": "b.pdf", "MimeType": "text/plain"},
            ],
        }
        _apply_file_overrides_to_conversational_inputs(inputs, overrides)
        assert att1.id == "new-1"
        assert att2.id == "new-2"


class TestApplyFileOverridesEdgeCases:
    """Edge cases for the override logic."""

    def test_file_override_without_full_name_is_not_indexed(self) -> None:
        """File dicts with ID but no FullName cannot match any attachment."""
        attachment = _make_attachment("old-id", "file.pdf")
        inputs = _make_conversational_inputs(current_prompt_attachments=[attachment])
        overrides = {"files": {"ID": "new-id"}}
        _apply_file_overrides_to_conversational_inputs(inputs, overrides)
        assert attachment.id == "old-id"

    def test_duplicate_full_names_last_wins(self) -> None:
        """When multiple overrides share the same FullName, the last one wins in the dict comprehension."""
        attachment = _make_attachment("old-id", "file.pdf")
        inputs = _make_conversational_inputs(current_prompt_attachments=[attachment])
        overrides = {
            "files": [
                {
                    "ID": "first-id",
                    "FullName": "file.pdf",
                    "MimeType": "application/pdf",
                },
                {"ID": "second-id", "FullName": "file.pdf", "MimeType": "text/plain"},
            ]
        }
        _apply_file_overrides_to_conversational_inputs(inputs, overrides)
        assert attachment.id == "second-id"
        assert attachment.mime_type == "text/plain"


class TestApplyFileOverridesConversationHistory:
    """Tests for overrides applied to conversation history attachments."""

    def test_override_applied_to_history_user_message(self) -> None:
        history_attachment = _make_attachment("old-hist", "history.pdf")
        history_msg = LegacyConversationalEvalUserMessage(
            role="user", text="past message", attachments=[history_attachment]
        )
        inputs = _make_conversational_inputs(
            conversation_history=[[history_msg]],
        )
        overrides = {
            "files": {
                "ID": "new-hist",
                "FullName": "history.pdf",
                "MimeType": "application/pdf",
            }
        }
        _apply_file_overrides_to_conversational_inputs(inputs, overrides)
        assert history_attachment.id == "new-hist"

    def test_override_applied_to_both_current_and_history(self) -> None:
        current_att = _make_attachment("old-curr", "current.pdf")
        history_att = _make_attachment("old-hist", "history.pdf")
        history_msg = LegacyConversationalEvalUserMessage(
            role="user", text="past message", attachments=[history_att]
        )
        inputs = _make_conversational_inputs(
            current_prompt_attachments=[current_att],
            conversation_history=[[history_msg]],
        )
        overrides = {
            "files": [
                {
                    "ID": "new-curr",
                    "FullName": "current.pdf",
                    "MimeType": "application/pdf",
                },
                {
                    "ID": "new-hist",
                    "FullName": "history.pdf",
                    "MimeType": "application/pdf",
                },
            ]
        }
        _apply_file_overrides_to_conversational_inputs(inputs, overrides)
        assert current_att.id == "new-curr"
        assert history_att.id == "new-hist"

    def test_agent_messages_without_attachments_are_skipped(self) -> None:
        """Agent messages don't have attachments; they should be safely iterated."""
        current_att = _make_attachment("old-id", "file.pdf")
        agent_msg = LegacyConversationalEvalInputAgentMessage(
            role="agent", text="agent response"
        )
        user_msg = LegacyConversationalEvalUserMessage(
            role="user", text="user follow-up", attachments=None
        )
        inputs = _make_conversational_inputs(
            current_prompt_attachments=[current_att],
            conversation_history=[[user_msg, agent_msg]],
        )
        overrides = {
            "files": {
                "ID": "new-id",
                "FullName": "file.pdf",
                "MimeType": "application/pdf",
            }
        }
        _apply_file_overrides_to_conversational_inputs(inputs, overrides)
        assert current_att.id == "new-id"

    def test_multiple_exchanges_in_history(self) -> None:
        att1 = _make_attachment("old-1", "first.pdf")
        att2 = _make_attachment("old-2", "second.pdf")
        exchange1 = [
            LegacyConversationalEvalUserMessage(
                role="user", text="msg1", attachments=[att1]
            ),
        ]
        exchange2 = [
            LegacyConversationalEvalUserMessage(
                role="user", text="msg2", attachments=[att2]
            ),
        ]
        inputs = _make_conversational_inputs(
            conversation_history=[exchange1, exchange2],
        )
        overrides = {
            "files": [
                {"ID": "new-1", "FullName": "first.pdf", "MimeType": "application/pdf"},
                {
                    "ID": "new-2",
                    "FullName": "second.pdf",
                    "MimeType": "application/pdf",
                },
            ]
        }
        _apply_file_overrides_to_conversational_inputs(inputs, overrides)
        assert att1.id == "new-1"
        assert att2.id == "new-2"
