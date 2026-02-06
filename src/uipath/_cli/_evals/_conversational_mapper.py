from typing import Any, Dict, List
from uipath.core.chat import UiPathConversationMessage

def to_conversational_eval_output_schema(
    messages: List[UiPathConversationMessage],
) -> Dict[str, Any]:
    """Convert list of messages to conversational eval output schema.

    Args:
        messages: List of message dictionaries with role, content, tool_calls, etc.

    Returns:
        Dict with structure: {"agentResponse": [{"text": str, "toolCalls": [...]}]}
    """
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