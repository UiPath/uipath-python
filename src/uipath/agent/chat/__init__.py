"""UiPath Chat Data Models.

This module defines Pydantic models for representing chat conversations between
users, system messages, AI assistants, and external tool calls. It provides
a structured schema for:

- **Citations**: References to external URLs or media (e.g., PDFs).
- **Content Parts**: Segments of a message's content, with MIME type and optional citations.
- **Tool Calls**: Representations of external tool/function invocations and their results.
- **Messages**: Complete chat messages, including role, content, and tool usage.

These models facilitate serialization, validation, and manipulation of chat data
within the UiPath ecosystem, enabling advanced conversational AI interactions
with rich context and external knowledge integration.
"""

from ._models import UiPathChatMessage, UiPathChatMessageRole

__all__ = ["UiPathChatMessage", "UiPathChatMessageRole"]
