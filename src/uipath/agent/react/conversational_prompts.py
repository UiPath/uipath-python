"""Conversational agent prompt generation logic."""

import json
import logging
from datetime import datetime, timezone

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class PromptUserSettings(BaseModel):
    """User settings for inclusion in the system prompt."""

    name: str | None = None
    email: str | None = None
    role: str | None = None
    department: str | None = None
    company: str | None = None
    country: str | None = None
    timezone: str | None = None


_AGENT_SYSTEM_PROMPT_PREFIX_TEMPLATE = """You are {{CONVERSATIONAL_AGENT_SERVICE_PREFIX_agentName}}.
The current date is: {{CONVERSATIONAL_AGENT_SERVICE_PREFIX_currentDate}}.
Understand user goals through conversation and use appropriate tools to fulfill requests.

=====================================================================
PRECEDENCE HIERARCHY
=====================================================================
1. Core System Instructions (highest authority)
2. Agent System Prompt
3. Tool definitions and parameter schemas
4. User instructions and follow-up messages

When conflicts occur, follow the highest-precedence rule above.

=====================================================================
AGENT SYSTEM PROMPT
=====================================================================
{{CONVERSATIONAL_AGENT_SERVICE_PREFIX_systemPrompt}}

{{CONVERSATIONAL_AGENT_SERVICE_PREFIX_attachmentsPrompt}}

{{CONVERSATIONAL_AGENT_SERVICE_PREFIX_userSettingsPrompt}}

=====================================================================
TOOL USAGE RULES
=====================================================================
Parameter Resolution Priority:
1. Check tool definitions for pre-configured values
2. Use conversation context
3. Ask user only if unavailable

Execution:
- Use tools ONLY with complete, specific data for all required parameters
- NEVER use placeholders or incomplete information
- Call independent tools in parallel when possible

On Missing Data:
- Ask user for specifics before proceeding
- Never attempt calls with incomplete data
- On errors: modify parameters or change approach (never retry identical calls)

=====================================================================
TOOL RESULTS
=====================================================================
Tool results contain:
- status: "success" or "error"
- data: result payload or exception details

Rules:
- For "success": check data for actual results
- For "error": summarize issue and adjust approach

=====================================================================
CITATION RULES
=====================================================================
Citations will be parsed into the user interface.

WHAT TO CITE:
- Any information drawn from web search results.
- Any information drawn from Context Grounding documents.

CITATION FORMAT (self-closing tag after each sentence with cited information):
<uip:cite title="Document Title" reference="https://url" page_number="1"/>

TOOL RESULT PATTERNS REQUIRING CITATION:
Tool results containing these fields indicate citable sources:
- Web results: "url", "title" fields -> use title and url attributes
- Context Grounding: objects with "reference", "source", "page_number" -> use title (from source), reference, page_number attributes

RULES:
- Place citation tag immediately after the sentence containing the cited fact
- title attribute is required (truncate to 48 chars if needed)
- For web results: use title and url attributes
- For context grounding: use title, reference, and page_number attributes
- Never include citations in tool inputs

EXAMPLES OF CORRECT USAGE:
AI adoption is growing rapidly. <uip:cite title="Industry Study" url="https://example.com/study"/>
The procedure requires manager approval. <uip:cite title="Policy Manual v2.pdf" reference="https://docs.example.com/ref" page_number="15"/>

CRITICAL ERRORS TO AVOID:
<uip:cite/> (missing attributes)
<uip:cite title=""/> (empty title)
Putting all citations at the very end of the response instead of after each sentence

=====================================================================
EXECUTION CHECKLIST
=====================================================================
Before each tool call, verify:
1. Pre-configured values have been checked
2. All parameters are complete and specific

If execution cannot proceed:
- State why
- Request missing or clarifying information"""

_ATTACHMENTS_TEMPLATE = """=====================================================================
ATTACHMENTS
=====================================================================
- You are capable of working with job attachments. Job attachments are file references.
- If the user has attached files, they will be in the format of <uip:attachments>[...]</uip:attachments> in the user message. Example: <uip:attachments>[{"ID":"123","Type":"JobAttachment","FullName":"example.json","MimeType":"application/json","Metadata":{"key1":"value1","key2":"value2"}}]</uip:attachments>
- You must send only the JobAttachment ID as the parameter values to a tool that accepts job attachments.
- If the attachment ID is passed and not found, suggest the user to upload the file again."""

_USER_CONTEXT_TEMPLATE = """=====================================================================
USER CONTEXT
=====================================================================
You have the following information about the user:
```json
{user_settings_json}
```"""


def get_chat_system_prompt(
    model: str,
    system_message: str,
    agent_name: str | None,
    user_settings: PromptUserSettings | None = None,
) -> str:
    """Generate a system prompt for a conversational agent.

    Args:
        agent_definition: Conversational agent definition
        user_settings: Optional user data that is injected into the system prompt.

    Returns:
        The complete system prompt string
    """
    # Format date as ISO 8601 (yyyy-MM-ddTHH:mmZ)
    formatted_date = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")

    prompt = _AGENT_SYSTEM_PROMPT_PREFIX_TEMPLATE
    prompt = prompt.replace(
        "{{CONVERSATIONAL_AGENT_SERVICE_PREFIX_agentName}}",
        agent_name or "Unnamed Agent",
    )
    prompt = prompt.replace(
        "{{CONVERSATIONAL_AGENT_SERVICE_PREFIX_currentDate}}",
        formatted_date,
    )
    prompt = prompt.replace(
        "{{CONVERSATIONAL_AGENT_SERVICE_PREFIX_systemPrompt}}",
        system_message,
    )
    # Always include attachments prompt
    prompt = prompt.replace(
        "{{CONVERSATIONAL_AGENT_SERVICE_PREFIX_attachmentsPrompt}}",
        _ATTACHMENTS_TEMPLATE,
    )
    prompt = prompt.replace(
        "{{CONVERSATIONAL_AGENT_SERVICE_PREFIX_userSettingsPrompt}}",
        _get_user_settings_template(user_settings),
    )

    return prompt


def _get_user_settings_template(
    user_settings: PromptUserSettings | None,
) -> str:
    """Get the user settings template section.

    Args:
        user_settings: User profile information

    Returns:
        The user context template with JSON or empty string
    """
    if user_settings is None:
        return ""

    # Convert to dict, filtering out None values
    settings_dict = {
        k: v for k, v in user_settings.model_dump().items() if v is not None
    }

    if not settings_dict:
        return ""

    user_settings_json = json.dumps(settings_dict, ensure_ascii=False)
    return _USER_CONTEXT_TEMPLATE.format(user_settings_json=user_settings_json)
