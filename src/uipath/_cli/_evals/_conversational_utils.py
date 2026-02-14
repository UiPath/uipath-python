from typing import Any, Dict, Literal, List
from datetime import datetime, timezone
import uuid
from uipath.core.chat import UiPathConversationMessage, UiPathConversationContentPart, UiPathConversationToolCall, UiPathConversationToolCallResult
from uipath.core.chat.content import UiPathInlineValue

from pydantic import BaseModel, Field

# Types for legacy conversational-agent evaluation input/outputs.

class LegacyConversationalEvalJobAttachmentReference(BaseModel):
    """File attachment reference in eval messages."""

    id: str
    full_name: str = Field(..., alias="fullName")
    mime_type: str = Field(..., alias="mimeType")


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
    attachments: list[LegacyConversationalEvalJobAttachmentReference] | None = Field(default=None)


class LegacyConversationalEvalInputAgentMessage(LegacyConversationalEvalMessage):
    """Agent message in eval input schema (input tool-calls contain results field)."""

    role: Literal["agent"] = "agent"
    tool_calls: list[LegacyConversationalEvalInputToolCall] | None = Field(default=None, alias="toolCalls")


class LegacyConversationalEvalOutputAgentMessage(LegacyConversationalEvalMessage):
    """Agent message in eval output schema (output tool-calls don't contain result field)."""

    role: Literal["agent"] = "agent"
    tool_calls: list[LegacyConversationalEvalOutputToolCall] = Field(default=None, alias="toolCalls")


class LegacyConversationalEvalInput(BaseModel):
    """Complete conversational eval input schema.

    conversationHistory: Array of exchanges, where each exchange is
                        [userMessage, ...agentMessages[]]
    currentUserPrompt: The current user message to evaluate
    """

    conversation_history: list[
        list[LegacyConversationalEvalUserMessage | LegacyConversationalEvalInputAgentMessage]
    ] = Field(alias="conversationHistory")
    current_user_prompt: LegacyConversationalEvalUserMessage = Field(alias="currentUserPrompt")

class LegacyConversationalEvalOutput(BaseModel):
    """Complete eval output schema matching TypeScript definition.

    agentResponse: Sequence of agent messages ending with a message without tool calls
    """

    agent_response: list[LegacyConversationalEvalOutputAgentMessage] = Field(alias="agentResponse")

# Mapper functions to convert between UiPath standard Message format and legacy conversational formats

class UiPathLegacyEvalChatMessagesMapper:
    @staticmethod
    def legacy_conversational_eval_input_to_messages(
        eval_input: LegacyConversationalEvalInput
    ) -> List[UiPathConversationMessage]:
        """Convert legacy eval input format to list of UiPathConversationMessage.

        Args:
            eval_input: Legacy conversational eval input with conversation_history and current_user_prompt

        Returns:
            List of UiPathConversationMessage objects representing the full conversation
        """
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


    # def messages_to_legacy_conversational_eval_output(
    #     messages: List[UiPathConversationMessage],
    # ) -> LegacyConversationalEvalOutput:
    #     """Convert list of UiPathConversationMessage to LegacyConversationalEvalOutput.

    #     Args:
    #         messages: List of UiPathConversationMessage objects

    #     Returns:
    #         LegacyConversationalEvalOutput containing agent response messages
    #     """
    #     agent_messages = []

    #     for message in messages:
    #         # Only process assistant/agent messages
    #         if message.role in ("assistant", "agent", "ai"):
    #             # Extract text from content parts
    #             text = ""
    #             if message.content_parts:
    #                 for content_part in message.content_parts:
    #                     if content_part.mime_type == "text/plain":
    #                         # Extract inline value
    #                         if hasattr(content_part.data, 'inline'):
    #                             text += str(content_part.data.inline)

    #             # Convert tool calls if present
    #             tool_calls = None
    #             if message.tool_calls:
    #                 tool_calls = []
    #                 for tc in message.tool_calls:
    #                     # Extract input arguments
    #                     arguments = {}
    #                     if tc.input:
    #                         if hasattr(tc.input, 'inline'):
    #                             arguments = tc.input.inline if isinstance(tc.input.inline, dict) else {}

    #                     tool_call = LegacyConversationalEvalOutputToolCall(
    #                         name=tc.name,
    #                         arguments=arguments,
    #                     )
    #                     tool_calls.append(tool_call)

    #             agent_message = LegacyConversationalEvalOutputAgentMessage(
    #                 role="agent",
    #                 text=text,
    #                 tool_calls=tool_calls,
    #             )
    #             agent_messages.append(agent_message)

    #     return LegacyConversationalEvalOutput(agent_response=agent_messages)


    # TODO Check on below. I think that messages_to_legacy_conversational_eval_output was converting
    # the core langgraph message and we would first need that to be converted into the UiPathConversationMessage.

    # def messages_to_legacy_conversational_eval_output_schema(
    #     messages: List[UiPathConversationMessage],
    # ) -> Dict[str, Any]:
    #     """Convert list of UiPathConversationMessage to legacy eval output schema dict.

    #     Args:
    #         messages: List of UiPathConversationMessage objects

    #     Returns:
    #         Dictionary matching LegacyConversationalEvalOutput schema (with camelCase keys)
    #     """
    #     output = messages_to_legacy_conversational_eval_output(messages)
    #     return output.model_dump(by_alias=True, exclude_none=True)

    @staticmethod
    def messages_to_legacy_conversational_eval_output(
        messages: List[UiPathConversationMessage],
    ) -> LegacyConversationalEvalOutput:
        """Convert list of messages to conversational eval output schema."""

        agent_messages = []

        for message in messages:
            if message.get("type") == "ai":
                tool_calls = []
                if message.get("tool_calls"):
                    tool_calls = [
                        {
                            "name": tc.get("name") or tc.get("function", {}).get("name"),
                            "arguments": tc.get("arguments")
                            or tc.get("function", {}).get("arguments"),
                        }
                        for tc in message["tool_calls"]
                    ]

                agent_message = {
                    "text": message.get("content") or "",
                    "toolCalls": tool_calls if tool_calls else None,
                }
                agent_messages.append(agent_message)

        return {"agentResponse": agent_messages}