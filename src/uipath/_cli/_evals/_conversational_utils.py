import uuid
from datetime import datetime, timezone
from typing import Any, List, Literal

from pydantic import BaseModel, Field
from uipath.core.chat import (
    UiPathConversationContentPart,
    UiPathConversationContentPartData,
    UiPathConversationMessage,
    UiPathConversationMessageData,
    UiPathConversationToolCall,
    UiPathConversationToolCallData,
    UiPathConversationToolCallResult,
    UiPathInlineValue,
)

# Types for legacy conversational-agent evaluation input/outputs.


class LegacyConversationalEvalJobAttachmentReference(BaseModel):
    """File attachment reference in eval messages."""

    id: str = Field(..., alias="ID")
    full_name: str = Field(..., alias="FullName")
    mime_type: str = Field(..., alias="MimeType")


class LegacyConversationalEvalOutputToolCall(BaseModel):
    """Tool call in eval output schema (no result field)."""

    name: str
    arguments: dict[str, Any]


class LegacyConversationalEvalInputToolCallResult(BaseModel):
    """Tool call result in eval input schema."""

    value: Any
    is_error: bool | None = Field(default=None, alias="isError")


class LegacyConversationalEvalInputToolCall(LegacyConversationalEvalOutputToolCall):
    """Tool call in eval input schema (extends output tool call with result)."""

    result: LegacyConversationalEvalInputToolCallResult


class LegacyConversationalEvalMessage(BaseModel):
    """Base eval message type."""

    role: Literal["agent", "user"]
    text: str


class LegacyConversationalEvalUserMessage(LegacyConversationalEvalMessage):
    """User message in eval schema."""

    role: Literal["user"] = "user"
    attachments: list[LegacyConversationalEvalJobAttachmentReference] | None = Field(
        default=None
    )


class LegacyConversationalEvalInputAgentMessage(LegacyConversationalEvalMessage):
    """Agent message in eval input schema (input tool-calls contain results field)."""

    role: Literal["agent"] = "agent"
    tool_calls: list[LegacyConversationalEvalInputToolCall] | None = Field(
        default=None, alias="toolCalls"
    )


class LegacyConversationalEvalOutputAgentMessage(LegacyConversationalEvalMessage):
    """Agent message in eval output schema (output tool-calls don't contain result field)."""

    role: Literal["agent"] = "agent"
    tool_calls: list[LegacyConversationalEvalOutputToolCall] | None = Field(
        default=None, alias="toolCalls"
    )


class LegacyConversationalEvalInput(BaseModel):
    """Complete conversational eval input schema.

    conversationHistory: Array of exchanges, where each exchange is
                        [userMessage, ...agentMessages[]]
    currentUserPrompt: The current user message to evaluate
    """

    conversation_history: list[
        list[
            LegacyConversationalEvalUserMessage
            | LegacyConversationalEvalInputAgentMessage
        ]
    ] = Field(alias="conversationHistory")
    current_user_prompt: LegacyConversationalEvalUserMessage = Field(
        alias="currentUserPrompt"
    )


class LegacyConversationalEvalOutput(BaseModel):
    """Complete eval output schema matching TypeScript definition.

    agentResponse: Sequence of agent messages ending with a message without tool calls
    """

    agent_response: list[LegacyConversationalEvalOutputAgentMessage] = Field(
        alias="agentResponse"
    )


# Mapper functions to convert between UiPath standard Message format and legacy conversational formats


class UiPathLegacyEvalChatMessagesMapper:
    @staticmethod
    def legacy_conversational_eval_input_to_uipath_message_list(
        eval_input: LegacyConversationalEvalInput,
    ) -> List[UiPathConversationMessage]:
        """Convert legacy eval input format to list of UiPathConversationMessage."""
        messages: List[UiPathConversationMessage] = []
        timestamp = (
            datetime.now(timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z")
        )

        # Process conversation history (list of exchanges)
        for eval_exchange in eval_input.conversation_history:
            for eval_message in eval_exchange:
                if eval_message.role == "user":
                    # Convert user message
                    content_parts = [
                        UiPathConversationContentPart(
                            content_part_id=str(uuid.uuid4()),
                            mime_type="text/plain",
                            data=UiPathInlineValue(inline=eval_message.text),
                            citations=[],
                            created_at=timestamp,
                            updated_at=timestamp,
                        )
                    ]

                    # TODO: Add attachments if present
                    # if message.attachments:
                    #     for attachment in message.attachments:
                    #         content_parts.append(
                    #             UiPathConversationContentPart(...)
                    #         )

                    messages.append(
                        UiPathConversationMessage(
                            message_id=str(uuid.uuid4()),
                            role="user",
                            content_parts=content_parts,
                            tool_calls=[],
                            interrupts=[],
                            created_at=timestamp,
                            updated_at=timestamp,
                        )
                    )
                elif eval_message.role == "agent":
                    # Convert agent message
                    content_parts = [
                        UiPathConversationContentPart(
                            content_part_id=str(uuid.uuid4()),
                            mime_type="text/markdown",
                            data=UiPathInlineValue(inline=eval_message.text),
                            citations=[],
                            created_at=timestamp,
                            updated_at=timestamp,
                        )
                    ]

                    # Convert tool calls if present
                    tool_calls: List[UiPathConversationToolCall] = []
                    if eval_message.tool_calls:
                        for tc in eval_message.tool_calls:
                            tool_call = UiPathConversationToolCall(
                                tool_call_id=str(uuid.uuid4()),
                                name=tc.name,
                                input=tc.arguments,
                                timestamp=timestamp,
                                result=UiPathConversationToolCallResult(
                                    timestamp=timestamp,
                                    output=tc.result.value,
                                    is_error=tc.result.is_error,
                                ),
                                created_at=timestamp,
                                updated_at=timestamp,
                            )
                            tool_calls.append(tool_call)

                    messages.append(
                        UiPathConversationMessage(
                            message_id=str(uuid.uuid4()),
                            role="assistant",
                            content_parts=content_parts,
                            tool_calls=tool_calls,
                            interrupts=[],
                            created_at=timestamp,
                            updated_at=timestamp,
                        )
                    )

        # Add current user prompt
        content_parts = [
            UiPathConversationContentPart(
                content_part_id=str(uuid.uuid4()),
                mime_type="text/plain",
                data=UiPathInlineValue(inline=eval_input.current_user_prompt.text),
                citations=[],
                created_at=timestamp,
                updated_at=timestamp,
            )
        ]

        # TODO Add attachments if present
        # if eval_input.current_user_prompt.attachments:
        #     for attachment in eval_input.current_user_prompt.attachments:
        #         content_parts.append(
        #             UiPathConversationContentPart(...)
        #         )

        messages.append(
            UiPathConversationMessage(
                message_id=str(uuid.uuid4()),
                role="user",
                content_parts=content_parts,
                tool_calls=[],
                interrupts=[],
                created_at=timestamp,
                updated_at=timestamp,
            )
        )

        return messages

    @staticmethod
    def legacy_conversational_eval_output_to_uipath_message_data_list(
        eval_output: LegacyConversationalEvalOutput,
    ) -> List[UiPathConversationMessageData]:
        """Convert legacy eval output format to list of UiPathConversationMessageData."""
        messages: List[UiPathConversationMessageData] = []

        for eval_agent_message in eval_output.agent_response:
            content_parts = [
                UiPathConversationContentPartData(
                    mime_type="text/markdown",
                    data=UiPathInlineValue(inline=eval_agent_message.text),
                    citations=[],
                )
            ]

            tool_calls: List[UiPathConversationToolCallData] = []
            if eval_agent_message.tool_calls:
                for tc in eval_agent_message.tool_calls:
                    tool_call = UiPathConversationToolCallData(
                        name=tc.name,
                        input=tc.arguments,
                    )
                    tool_calls.append(tool_call)

            messages.append(
                UiPathConversationMessageData(
                    role="assistant",
                    content_parts=content_parts,
                    tool_calls=tool_calls,
                    interrupts=[],
                )
            )

        return messages
