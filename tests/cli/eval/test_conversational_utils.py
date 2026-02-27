"""Tests for conversational eval utilities."""

from uipath._cli._evals._conversational_utils import (
    LegacyConversationalEvalInput,
    LegacyConversationalEvalInputAgentMessage,
    LegacyConversationalEvalInputToolCall,
    LegacyConversationalEvalInputToolCallResult,
    LegacyConversationalEvalJobAttachmentReference,
    LegacyConversationalEvalOutput,
    LegacyConversationalEvalOutputAgentMessage,
    LegacyConversationalEvalOutputToolCall,
    LegacyConversationalEvalUserMessage,
    UiPathLegacyEvalChatMessagesMapper,
)
from uipath.core.chat import UiPathExternalValue, UiPathInlineValue


class TestLegacyConversationalEvalInputToUiPathMessages:
    """Tests for converting legacy eval input to UiPath messages."""

    def test_converts_simple_conversation(self):
        """Should convert simple user-agent conversation."""
        eval_input = LegacyConversationalEvalInput(
            conversationHistory=[
                [
                    LegacyConversationalEvalUserMessage(text="Hello"),
                    LegacyConversationalEvalInputAgentMessage(text="Hi there!"),
                ]
            ],
            currentUserPrompt=LegacyConversationalEvalUserMessage(text="How are you?"),
        )

        result = UiPathLegacyEvalChatMessagesMapper.legacy_conversational_eval_input_to_uipath_message_list(
            eval_input
        )

        # Should have 3 messages: user, agent, user
        assert len(result) == 3
        assert result[0].role == "user"
        assert isinstance(result[0].content_parts[0].data, UiPathInlineValue)
        assert result[0].content_parts[0].data.inline == "Hello"
        assert result[1].role == "assistant"
        assert isinstance(result[1].content_parts[0].data, UiPathInlineValue)
        assert result[1].content_parts[0].data.inline == "Hi there!"
        assert result[2].role == "user"
        assert isinstance(result[2].content_parts[0].data, UiPathInlineValue)
        assert result[2].content_parts[0].data.inline == "How are you?"

    def test_converts_user_message_with_text_plain_mime_type(self):
        """User messages should have text/plain mime type."""
        eval_input = LegacyConversationalEvalInput(
            conversationHistory=[],
            currentUserPrompt=LegacyConversationalEvalUserMessage(text="Test"),
        )

        result = UiPathLegacyEvalChatMessagesMapper.legacy_conversational_eval_input_to_uipath_message_list(
            eval_input
        )

        assert len(result) == 1
        assert result[0].content_parts[0].mime_type == "text/plain"

    def test_converts_agent_message_with_text_markdown_mime_type(self):
        """Agent messages should have text/markdown mime type."""
        eval_input = LegacyConversationalEvalInput(
            conversationHistory=[
                [
                    LegacyConversationalEvalUserMessage(text="Question"),
                    LegacyConversationalEvalInputAgentMessage(text="**Answer**"),
                ]
            ],
            currentUserPrompt=LegacyConversationalEvalUserMessage(text="Next"),
        )

        result = UiPathLegacyEvalChatMessagesMapper.legacy_conversational_eval_input_to_uipath_message_list(
            eval_input
        )

        # Agent message is at index 1
        assert result[1].content_parts[0].mime_type == "text/markdown"

    def test_converts_agent_message_with_tool_calls(self):
        """Should convert agent messages with tool calls and results."""
        eval_input = LegacyConversationalEvalInput(
            conversationHistory=[
                [
                    LegacyConversationalEvalUserMessage(text="Search for data"),
                    LegacyConversationalEvalInputAgentMessage(
                        text="Let me search",
                        toolCalls=[
                            LegacyConversationalEvalInputToolCall(
                                name="search_tool",
                                arguments={"query": "test"},
                                result=LegacyConversationalEvalInputToolCallResult(
                                    value={"results": ["item1", "item2"]},
                                    isError=False,
                                ),
                            )
                        ],
                    ),
                ]
            ],
            currentUserPrompt=LegacyConversationalEvalUserMessage(text="Thanks"),
        )

        result = UiPathLegacyEvalChatMessagesMapper.legacy_conversational_eval_input_to_uipath_message_list(
            eval_input
        )

        agent_message = result[1]
        assert agent_message.role == "assistant"
        assert len(agent_message.tool_calls) == 1
        assert agent_message.tool_calls[0].name == "search_tool"
        assert agent_message.tool_calls[0].input == {"query": "test"}
        assert agent_message.tool_calls[0].result is not None
        assert agent_message.tool_calls[0].result.output == {
            "results": ["item1", "item2"]
        }
        assert agent_message.tool_calls[0].result.is_error is False

    def test_converts_tool_call_with_error_result(self):
        """Should handle tool calls with error results."""
        eval_input = LegacyConversationalEvalInput(
            conversationHistory=[
                [
                    LegacyConversationalEvalUserMessage(text="Do something"),
                    LegacyConversationalEvalInputAgentMessage(
                        text="Trying",
                        toolCalls=[
                            LegacyConversationalEvalInputToolCall(
                                name="failing_tool",
                                arguments={},
                                result=LegacyConversationalEvalInputToolCallResult(
                                    value="Error occurred",
                                    isError=True,
                                ),
                            )
                        ],
                    ),
                ]
            ],
            currentUserPrompt=LegacyConversationalEvalUserMessage(text="Ok"),
        )

        result = UiPathLegacyEvalChatMessagesMapper.legacy_conversational_eval_input_to_uipath_message_list(
            eval_input
        )

        tool_call = result[1].tool_calls[0]
        assert tool_call.result is not None
        assert tool_call.result.is_error is True
        assert tool_call.result.output == "Error occurred"

    def test_converts_multiple_exchanges(self):
        """Should handle multiple conversation exchanges."""
        eval_input = LegacyConversationalEvalInput(
            conversationHistory=[
                [
                    LegacyConversationalEvalUserMessage(text="First question"),
                    LegacyConversationalEvalInputAgentMessage(text="First answer"),
                ],
                [
                    LegacyConversationalEvalUserMessage(text="Second question"),
                    LegacyConversationalEvalInputAgentMessage(text="Second answer"),
                ],
            ],
            currentUserPrompt=LegacyConversationalEvalUserMessage(
                text="Third question"
            ),
        )

        result = UiPathLegacyEvalChatMessagesMapper.legacy_conversational_eval_input_to_uipath_message_list(
            eval_input
        )

        assert len(result) == 5  # 2 exchanges (4 messages) + current prompt
        assert isinstance(result[0].content_parts[0].data, UiPathInlineValue)
        assert result[0].content_parts[0].data.inline == "First question"
        assert isinstance(result[1].content_parts[0].data, UiPathInlineValue)
        assert result[1].content_parts[0].data.inline == "First answer"
        assert isinstance(result[2].content_parts[0].data, UiPathInlineValue)
        assert result[2].content_parts[0].data.inline == "Second question"
        assert isinstance(result[3].content_parts[0].data, UiPathInlineValue)
        assert result[3].content_parts[0].data.inline == "Second answer"
        assert isinstance(result[4].content_parts[0].data, UiPathInlineValue)
        assert result[4].content_parts[0].data.inline == "Third question"

    def test_converts_exchange_with_multiple_agent_messages(self):
        """Should handle exchanges with multiple agent responses."""
        eval_input = LegacyConversationalEvalInput(
            conversationHistory=[
                [
                    LegacyConversationalEvalUserMessage(text="Question"),
                    LegacyConversationalEvalInputAgentMessage(
                        text="Using tool",
                        toolCalls=[
                            LegacyConversationalEvalInputToolCall(
                                name="tool1",
                                arguments={"x": 1},
                                result=LegacyConversationalEvalInputToolCallResult(
                                    value="result1",
                                    isError=False,
                                ),
                            )
                        ],
                    ),
                    LegacyConversationalEvalInputAgentMessage(text="Final answer"),
                ]
            ],
            currentUserPrompt=LegacyConversationalEvalUserMessage(text="Next"),
        )

        result = UiPathLegacyEvalChatMessagesMapper.legacy_conversational_eval_input_to_uipath_message_list(
            eval_input
        )

        assert len(result) == 4  # user, agent with tool, agent final, current user
        assert result[0].role == "user"
        assert result[1].role == "assistant"
        assert len(result[1].tool_calls) == 1
        assert result[2].role == "assistant"
        assert len(result[2].tool_calls) == 0
        assert result[3].role == "user"

    def test_generates_unique_ids_for_messages(self):
        """Should generate unique message IDs."""
        eval_input = LegacyConversationalEvalInput(
            conversationHistory=[
                [
                    LegacyConversationalEvalUserMessage(text="Q1"),
                    LegacyConversationalEvalInputAgentMessage(text="A1"),
                ]
            ],
            currentUserPrompt=LegacyConversationalEvalUserMessage(text="Q2"),
        )

        result = UiPathLegacyEvalChatMessagesMapper.legacy_conversational_eval_input_to_uipath_message_list(
            eval_input
        )

        message_ids = [msg.message_id for msg in result]
        assert len(message_ids) == len(set(message_ids))  # All unique

    def test_generates_unique_content_part_ids(self):
        """Should generate unique content part IDs."""
        eval_input = LegacyConversationalEvalInput(
            conversationHistory=[
                [
                    LegacyConversationalEvalUserMessage(text="Q"),
                    LegacyConversationalEvalInputAgentMessage(text="A"),
                ]
            ],
            currentUserPrompt=LegacyConversationalEvalUserMessage(text="Q2"),
        )

        result = UiPathLegacyEvalChatMessagesMapper.legacy_conversational_eval_input_to_uipath_message_list(
            eval_input
        )

        content_part_ids = [
            part.content_part_id for msg in result for part in msg.content_parts
        ]
        assert len(content_part_ids) == len(set(content_part_ids))

    def test_empty_conversation_history(self):
        """Should handle empty conversation history."""
        eval_input = LegacyConversationalEvalInput(
            conversationHistory=[],
            currentUserPrompt=LegacyConversationalEvalUserMessage(text="First message"),
        )

        result = UiPathLegacyEvalChatMessagesMapper.legacy_conversational_eval_input_to_uipath_message_list(
            eval_input
        )

        assert len(result) == 1
        assert result[0].role == "user"
        assert isinstance(result[0].content_parts[0].data, UiPathInlineValue)
        assert result[0].content_parts[0].data.inline == "First message"

    def test_blank_text_in_message_creates_empty_content_parts(self):
        """Should create empty content_parts when user message has blank text."""
        eval_input = LegacyConversationalEvalInput(
            conversationHistory=[
                [
                    LegacyConversationalEvalUserMessage(text=""),
                    LegacyConversationalEvalInputAgentMessage(text=""),
                ]
            ],
            currentUserPrompt=LegacyConversationalEvalUserMessage(text=""),
        )

        result = UiPathLegacyEvalChatMessagesMapper.legacy_conversational_eval_input_to_uipath_message_list(
            eval_input
        )

        # Empty text content should result in no text content-parts
        assert len(result[0].content_parts) == 0
        assert len(result[1].content_parts) == 0
        assert len(result[2].content_parts) == 0

    def test_blank_text_with_tool_calls_creates_empty_content_parts(self):
        """Should create empty content_parts when agent message with tool calls has blank text."""
        eval_input = LegacyConversationalEvalInput(
            conversationHistory=[
                [
                    LegacyConversationalEvalUserMessage(text="Search for data"),
                    LegacyConversationalEvalInputAgentMessage(
                        text="",
                        toolCalls=[
                            LegacyConversationalEvalInputToolCall(
                                name="search_tool",
                                arguments={"query": "test"},
                                result=LegacyConversationalEvalInputToolCallResult(
                                    value={"results": ["item1"]},
                                    isError=False,
                                ),
                            )
                        ],
                    ),
                ]
            ],
            currentUserPrompt=LegacyConversationalEvalUserMessage(text="Thanks"),
        )

        result = UiPathLegacyEvalChatMessagesMapper.legacy_conversational_eval_input_to_uipath_message_list(
            eval_input
        )

        agent_message = result[1]
        assert agent_message.role == "assistant"
        # Empty content should result in no text content-parts
        assert len(agent_message.content_parts) == 0
        # Tool calls should still be present
        assert len(agent_message.tool_calls) == 1

    def test_converts_user_message_with_single_attachment(self):
        """Should convert user message with a single attachment to UiPathExternalValue content part."""
        eval_input = LegacyConversationalEvalInput(
            conversationHistory=[
                [
                    LegacyConversationalEvalUserMessage(
                        text="See attached",
                        attachments=[
                            LegacyConversationalEvalJobAttachmentReference(
                                ID="abc-123",
                                FullName="report.pdf",
                                MimeType="application/pdf",
                            )
                        ],
                    ),
                    LegacyConversationalEvalInputAgentMessage(text="Got it"),
                ]
            ],
            currentUserPrompt=LegacyConversationalEvalUserMessage(text="Next"),
        )

        result = UiPathLegacyEvalChatMessagesMapper.legacy_conversational_eval_input_to_uipath_message_list(
            eval_input
        )

        user_msg = result[0]
        assert len(user_msg.content_parts) == 2
        # First part is text
        assert isinstance(user_msg.content_parts[0].data, UiPathInlineValue)
        assert user_msg.content_parts[0].data.inline == "See attached"
        # Second part is attachment
        assert isinstance(user_msg.content_parts[1].data, UiPathExternalValue)
        assert (
            user_msg.content_parts[1].data.uri
            == "urn:uipath:cas:file:orchestrator:abc-123"
        )
        assert user_msg.content_parts[1].name == "report.pdf"
        assert user_msg.content_parts[1].mime_type == "application/pdf"

    def test_converts_user_message_with_multiple_attachments(self):
        """Should convert user message with multiple attachments."""
        eval_input = LegacyConversationalEvalInput(
            conversationHistory=[
                [
                    LegacyConversationalEvalUserMessage(
                        text="Here are the files",
                        attachments=[
                            LegacyConversationalEvalJobAttachmentReference(
                                ID="id-1",
                                FullName="file1.csv",
                                MimeType="text/csv",
                            ),
                            LegacyConversationalEvalJobAttachmentReference(
                                ID="id-2",
                                FullName="file2.xlsx",
                                MimeType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            ),
                        ],
                    ),
                    LegacyConversationalEvalInputAgentMessage(text="Received"),
                ]
            ],
            currentUserPrompt=LegacyConversationalEvalUserMessage(text="Analyze"),
        )

        result = UiPathLegacyEvalChatMessagesMapper.legacy_conversational_eval_input_to_uipath_message_list(
            eval_input
        )

        user_msg = result[0]
        assert len(user_msg.content_parts) == 3  # 1 text + 2 attachments
        assert isinstance(user_msg.content_parts[1].data, UiPathExternalValue)
        assert (
            user_msg.content_parts[1].data.uri
            == "urn:uipath:cas:file:orchestrator:id-1"
        )
        assert user_msg.content_parts[1].name == "file1.csv"
        assert isinstance(user_msg.content_parts[2].data, UiPathExternalValue)
        assert (
            user_msg.content_parts[2].data.uri
            == "urn:uipath:cas:file:orchestrator:id-2"
        )
        assert user_msg.content_parts[2].name == "file2.xlsx"

    def test_converts_current_user_prompt_with_attachment(self):
        """Should convert current user prompt attachments."""
        eval_input = LegacyConversationalEvalInput(
            conversationHistory=[],
            currentUserPrompt=LegacyConversationalEvalUserMessage(
                text="Process this",
                attachments=[
                    LegacyConversationalEvalJobAttachmentReference(
                        ID="prompt-att-1",
                        FullName="data.json",
                        MimeType="application/json",
                    )
                ],
            ),
        )

        result = UiPathLegacyEvalChatMessagesMapper.legacy_conversational_eval_input_to_uipath_message_list(
            eval_input
        )

        assert len(result) == 1
        prompt_msg = result[0]
        assert len(prompt_msg.content_parts) == 2
        assert isinstance(prompt_msg.content_parts[1].data, UiPathExternalValue)
        assert (
            prompt_msg.content_parts[1].data.uri
            == "urn:uipath:cas:file:orchestrator:prompt-att-1"
        )
        assert prompt_msg.content_parts[1].name == "data.json"
        assert prompt_msg.content_parts[1].mime_type == "application/json"

    def test_user_message_with_no_attachments_unchanged(self):
        """Should not add attachment content parts when attachments is None."""
        eval_input = LegacyConversationalEvalInput(
            conversationHistory=[
                [
                    LegacyConversationalEvalUserMessage(
                        text="No attachments here", attachments=None
                    ),
                    LegacyConversationalEvalInputAgentMessage(text="Ok"),
                ]
            ],
            currentUserPrompt=LegacyConversationalEvalUserMessage(text="Done"),
        )

        result = UiPathLegacyEvalChatMessagesMapper.legacy_conversational_eval_input_to_uipath_message_list(
            eval_input
        )

        user_msg = result[0]
        assert len(user_msg.content_parts) == 1
        assert isinstance(user_msg.content_parts[0].data, UiPathInlineValue)

    def test_user_message_with_empty_text_and_attachment(self):
        """Should create only attachment content part when text is empty."""
        eval_input = LegacyConversationalEvalInput(
            conversationHistory=[
                [
                    LegacyConversationalEvalUserMessage(
                        text="",
                        attachments=[
                            LegacyConversationalEvalJobAttachmentReference(
                                ID="att-only",
                                FullName="image.png",
                                MimeType="image/png",
                            )
                        ],
                    ),
                    LegacyConversationalEvalInputAgentMessage(text="I see the image"),
                ]
            ],
            currentUserPrompt=LegacyConversationalEvalUserMessage(text="Thanks"),
        )

        result = UiPathLegacyEvalChatMessagesMapper.legacy_conversational_eval_input_to_uipath_message_list(
            eval_input
        )

        user_msg = result[0]
        # No text part (empty text), only attachment
        assert len(user_msg.content_parts) == 1
        assert isinstance(user_msg.content_parts[0].data, UiPathExternalValue)
        assert (
            user_msg.content_parts[0].data.uri
            == "urn:uipath:cas:file:orchestrator:att-only"
        )
        assert user_msg.content_parts[0].name == "image.png"

    def test_attachment_content_parts_have_unique_ids(self):
        """Should generate unique content part IDs for attachment parts."""
        eval_input = LegacyConversationalEvalInput(
            conversationHistory=[
                [
                    LegacyConversationalEvalUserMessage(
                        text="Files",
                        attachments=[
                            LegacyConversationalEvalJobAttachmentReference(
                                ID="a1",
                                FullName="f1.txt",
                                MimeType="text/plain",
                            ),
                            LegacyConversationalEvalJobAttachmentReference(
                                ID="a2",
                                FullName="f2.txt",
                                MimeType="text/plain",
                            ),
                        ],
                    ),
                    LegacyConversationalEvalInputAgentMessage(text="Ok"),
                ]
            ],
            currentUserPrompt=LegacyConversationalEvalUserMessage(
                text="More",
                attachments=[
                    LegacyConversationalEvalJobAttachmentReference(
                        ID="a3",
                        FullName="f3.txt",
                        MimeType="text/plain",
                    )
                ],
            ),
        )

        result = UiPathLegacyEvalChatMessagesMapper.legacy_conversational_eval_input_to_uipath_message_list(
            eval_input
        )

        all_ids = [
            part.content_part_id for msg in result for part in msg.content_parts
        ]
        assert len(all_ids) == len(set(all_ids))


class TestLegacyConversationalEvalOutputToUiPathMessageData:
    """Tests for converting legacy eval output to UiPath message data."""

    def test_converts_simple_agent_response(self):
        """Should convert simple agent response."""
        eval_output = LegacyConversationalEvalOutput(
            agentResponse=[
                LegacyConversationalEvalOutputAgentMessage(text="Here is the answer")
            ]
        )

        result = UiPathLegacyEvalChatMessagesMapper.legacy_conversational_eval_output_to_uipath_message_data_list(
            eval_output
        )

        assert len(result) == 1
        assert result[0].role == "assistant"
        assert len(result[0].content_parts) == 1
        assert isinstance(result[0].content_parts[0].data, UiPathInlineValue)
        assert result[0].content_parts[0].data.inline == "Here is the answer"
        assert result[0].content_parts[0].mime_type == "text/markdown"

    def test_converts_agent_response_with_tool_calls(self):
        """Should convert agent responses with tool calls."""
        eval_output = LegacyConversationalEvalOutput(
            agentResponse=[
                LegacyConversationalEvalOutputAgentMessage(
                    text="Using tool",
                    toolCalls=[
                        LegacyConversationalEvalOutputToolCall(
                            name="search",
                            arguments={"query": "test"},
                        )
                    ],
                )
            ]
        )

        result = UiPathLegacyEvalChatMessagesMapper.legacy_conversational_eval_output_to_uipath_message_data_list(
            eval_output
        )

        assert len(result) == 1
        assert len(result[0].tool_calls) == 1
        assert result[0].tool_calls[0].name == "search"
        assert result[0].tool_calls[0].input == {"query": "test"}
        # Output tool calls should not have result field
        assert result[0].tool_calls[0].result is None

    def test_converts_multiple_agent_messages(self):
        """Should convert multiple agent messages in sequence."""
        eval_output = LegacyConversationalEvalOutput(
            agentResponse=[
                LegacyConversationalEvalOutputAgentMessage(
                    text="First response",
                    toolCalls=[
                        LegacyConversationalEvalOutputToolCall(
                            name="tool1",
                            arguments={},
                        )
                    ],
                ),
                LegacyConversationalEvalOutputAgentMessage(text="Final response"),
            ]
        )

        result = UiPathLegacyEvalChatMessagesMapper.legacy_conversational_eval_output_to_uipath_message_data_list(
            eval_output
        )

        assert len(result) == 2
        assert isinstance(result[0].content_parts[0].data, UiPathInlineValue)
        assert result[0].content_parts[0].data.inline == "First response"
        assert len(result[0].tool_calls) == 1
        assert isinstance(result[1].content_parts[0].data, UiPathInlineValue)
        assert result[1].content_parts[0].data.inline == "Final response"
        assert len(result[1].tool_calls) == 0

    def test_converts_multiple_tool_calls_in_message(self):
        """Should handle multiple tool calls in a single message."""
        eval_output = LegacyConversationalEvalOutput(
            agentResponse=[
                LegacyConversationalEvalOutputAgentMessage(
                    text="Using multiple tools",
                    toolCalls=[
                        LegacyConversationalEvalOutputToolCall(
                            name="tool1",
                            arguments={"a": 1},
                        ),
                        LegacyConversationalEvalOutputToolCall(
                            name="tool2",
                            arguments={"b": 2},
                        ),
                    ],
                )
            ]
        )

        result = UiPathLegacyEvalChatMessagesMapper.legacy_conversational_eval_output_to_uipath_message_data_list(
            eval_output
        )

        assert len(result) == 1
        assert len(result[0].tool_calls) == 2
        assert result[0].tool_calls[0].name == "tool1"
        assert result[0].tool_calls[0].input == {"a": 1}
        assert result[0].tool_calls[1].name == "tool2"
        assert result[0].tool_calls[1].input == {"b": 2}

    def test_agent_message_without_tool_calls(self):
        """Should handle agent messages without tool calls."""
        eval_output = LegacyConversationalEvalOutput(
            agentResponse=[
                LegacyConversationalEvalOutputAgentMessage(text="Simple response")
            ]
        )

        result = UiPathLegacyEvalChatMessagesMapper.legacy_conversational_eval_output_to_uipath_message_data_list(
            eval_output
        )

        assert len(result) == 1
        assert len(result[0].tool_calls) == 0

    def test_empty_agent_response(self):
        """Should handle empty agent response list."""
        eval_output = LegacyConversationalEvalOutput(agentResponse=[])

        result = UiPathLegacyEvalChatMessagesMapper.legacy_conversational_eval_output_to_uipath_message_data_list(
            eval_output
        )

        assert result == []

    def test_preserves_empty_tool_arguments(self):
        """Should preserve empty tool arguments dict."""
        eval_output = LegacyConversationalEvalOutput(
            agentResponse=[
                LegacyConversationalEvalOutputAgentMessage(
                    text="Using tool",
                    toolCalls=[
                        LegacyConversationalEvalOutputToolCall(
                            name="no_arg_tool",
                            arguments={},
                        )
                    ],
                )
            ]
        )

        result = UiPathLegacyEvalChatMessagesMapper.legacy_conversational_eval_output_to_uipath_message_data_list(
            eval_output
        )

        assert result[0].tool_calls[0].input == {}

    def test_blank_text_in_agent_response_creates_empty_content_parts(self):
        """Should create empty content_parts when agent response has blank text."""
        eval_output = LegacyConversationalEvalOutput(
            agentResponse=[LegacyConversationalEvalOutputAgentMessage(text="")]
        )

        result = UiPathLegacyEvalChatMessagesMapper.legacy_conversational_eval_output_to_uipath_message_data_list(
            eval_output
        )

        assert len(result) == 1
        assert result[0].role == "assistant"
        # Empty text should result in no text content-parts
        assert len(result[0].content_parts) == 0

    def test_blank_text_with_tool_calls_in_agent_response_creates_empty_content_parts(
        self,
    ):
        """Should create empty content_parts when agent response with tool calls has blank text."""
        eval_output = LegacyConversationalEvalOutput(
            agentResponse=[
                LegacyConversationalEvalOutputAgentMessage(
                    text="",
                    toolCalls=[
                        LegacyConversationalEvalOutputToolCall(
                            name="search",
                            arguments={"query": "test"},
                        )
                    ],
                )
            ]
        )

        result = UiPathLegacyEvalChatMessagesMapper.legacy_conversational_eval_output_to_uipath_message_data_list(
            eval_output
        )

        assert len(result) == 1
        # Empty text should result in no text content-parts
        assert len(result[0].content_parts) == 0
        # Tool calls should still be present
        assert len(result[0].tool_calls) == 1
