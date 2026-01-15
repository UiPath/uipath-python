"""Conversational agent prompt generation logic."""

import json
import logging
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class CitationType(Enum):
    """Citation type for system prompt generation.

    Some models may have issues wrapping citation tags around text.
    In those cases, we can prompt the citation tags to be placed after the text instead.
    We also allow disabling citations entirely, for scenarios such as voice output.
    """

    NONE = "none"
    WRAPPED = "wrapped"
    TRAILING = "trailing"


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

CITATION FORMAT:
{{CONVERSATIONAL_AGENT_SERVICE_PREFIX_citationFormatPrompt}}

TOOL RESULT PATTERNS REQUIRING CITATION:
Tool results containing these fields indicate citable sources:
- Web results: "url", "title" fields
- Context Grounding: objects with "reference", "source", "page_number", "content"

SOURCE FORMATS:
- URLs: {"title":"Page Title","url":"https://example.com"}
- Context Grounding: {"title":"filename.pdf","reference":"https://ref.url","page_number":1}
  where title is set to the document source (filename), and reference and page_number
  are from the tool results

RULES:
- Minimum 1 source per citation (never empty array)
- Truncate titles >48 chars
- Never include citations in tool inputs

{{CONVERSATIONAL_AGENT_SERVICE_PREFIX_citationExamplePrompt}}

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

_CITATION_FORMAT_WRAPPED = "<uip:cite sources='[...]'>factual claim here</uip:cite>"
_CITATION_FORMAT_TRAILING = "factual claim here<uip:cite sources='[...]'></uip:cite>"

_CITATION_EXAMPLE_WRAPPED = """EXAMPLES OF CORRECT USAGE:
<uip:cite sources='[{"title":"Study","url":"https://example.com"}]'>AI adoption is growing</uip:cite>

CRITICAL ERRORS TO AVOID:
<uip:cite sources='[]'>text</uip:cite> (empty sources)
Some text<uip:cite sources='[...]'>part</uip:cite>more text (spacing)
<uip:cite sources='[...]'></uip:cite> (empty claim)"""

_CITATION_EXAMPLE_TRAILING = """EXAMPLES OF CORRECT USAGE:
AI adoption is growing<uip:cite sources='[{"title":"Study","url":"https://example.com"}]'></uip:cite>

CRITICAL ERRORS TO AVOID:
text<uip:cite sources='[]'></uip:cite> (empty sources)
Some text<uip:cite sources='[...]'>part</uip:cite>more text (content between citation tags)"""


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
    # Determine citation type based on model
    citation_type = _get_citation_type(model)

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
    prompt = prompt.replace(
        "{{CONVERSATIONAL_AGENT_SERVICE_PREFIX_citationFormatPrompt}}",
        _get_citation_format_prompt(citation_type),
    )
    prompt = prompt.replace(
        "{{CONVERSATIONAL_AGENT_SERVICE_PREFIX_citationExamplePrompt}}",
        _get_citation_example_prompt(citation_type),
    )

    return prompt


def _get_citation_type(model: str) -> CitationType:
    """Determine the citation type based on the agent's model.

    GPT models use trailing citations due to issues with generating
    wrapped citations around text.

    Args:
        model: The model name

    Returns:
        CitationType.TRAILING for GPT models, CitationType.WRAPPED otherwise
    """
    if "gpt" in model.lower():
        return CitationType.TRAILING
    return CitationType.WRAPPED


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


def _get_citation_format_prompt(citation_type: CitationType) -> str:
    """Get the citation format prompt based on citation type.

    Args:
        citation_type: The type of citation formatting to use

    Returns:
        The citation format string or empty string for NONE
    """
    if citation_type == CitationType.WRAPPED:
        return _CITATION_FORMAT_WRAPPED
    elif citation_type == CitationType.TRAILING:
        return _CITATION_FORMAT_TRAILING
    return ""


def _get_citation_example_prompt(citation_type: CitationType) -> str:
    """Get the citation example prompt based on citation type.

    Args:
        citation_type: The type of citation formatting to use

    Returns:
        The citation examples string or empty string for NONE
    """
    if citation_type == CitationType.WRAPPED:
        return _CITATION_EXAMPLE_WRAPPED
    elif citation_type == CitationType.TRAILING:
        return _CITATION_EXAMPLE_TRAILING
    return ""
