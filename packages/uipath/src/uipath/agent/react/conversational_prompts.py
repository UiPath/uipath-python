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
Current date and time (UTC, rounded down to the hour): {{CONVERSATIONAL_AGENT_SERVICE_PREFIX_currentDate}}
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

{{CONVERSATIONAL_AGENT_SERVICE_PREFIX_conversationIdPrompt}}

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
- Web results: <uip:cite title="Document Title" url="https://url"/>
- Context Grounding: <uip:cite title="Document Title" reference="https://url" page_number="1"/>

TOOL RESULT PATTERNS REQUIRING CITATION:
Tool results containing these fields indicate citable sources:
- Web results: "url", "title" fields -> use url, title attributes
- Context Grounding: objects with "reference", "source", "page_number" -> use reference, title (from source), page_number attributes

RULES:
- Place citation tag immediately after the sentence containing the cited fact
- title attribute is required (truncate to 48 chars if needed)
- For web results: use title and url attributes
- For context grounding: use title, reference, and page_number attributes
- Never include citations in tool inputs
- Do not mix attributes between citation types: web results use only title/url, context grounding uses only title/reference/page_number
- Do not add a space before the citation tag

EXAMPLES OF CORRECT USAGE:
AI adoption is growing rapidly.<uip:cite title="Industry Study" url="https://example.com/study"/>
The procedure requires manager approval.<uip:cite title="Policy Manual v2.pdf" reference="https://docs.example.com/ref" page_number="15"/>

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
- Request missing or clarifying information

{{CONVERSATIONAL_AGENT_SERVICE_PREFIX_outputSchemaHintPrompt}}"""

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

_CONVERSATION_ID_TEMPLATE = """
The current conversation ID is {conversation_id}. This may be useful to include in tool-calls when tool parameters specify passing in the conversation ID. Other than tool-call inputs, this ID should not be mentioned to the user.
"""


def get_chat_system_prompt(
    model: str,
    system_message: str,
    agent_name: str | None,
    user_settings: PromptUserSettings | None = None,
    conversation_id: str | None = None,
    output_schema: type[BaseModel] | None = None,
) -> str:
    """Generate a system prompt for a conversational agent.

    Args:
        model: Model identifier.
        system_message: The agent system prompt content.
        agent_name: The agent display name; defaults to "Unnamed Agent" when None.
        user_settings: Optional user data that is injected into the system prompt.
        conversation_id: Optional conversation identifier that is injected into the system prompt.
        output_schema: Optional structured output fields recorded after the conversational turn loop.

    Returns:
        The complete system prompt string
    """
    # Truncated to the hour to increase prompt-caching hits
    now = datetime.now(timezone.utc)
    formatted_date = f"{now:%A, %B} {now.day}, {now:%Y}, {now:%H}:00 UTC"

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
        get_user_settings_template(user_settings),
    )
    prompt = prompt.replace(
        "{{CONVERSATIONAL_AGENT_SERVICE_PREFIX_conversationIdPrompt}}",
        get_conversation_id_template(conversation_id),
    )

    prompt = prompt.replace(
        "{{CONVERSATIONAL_AGENT_SERVICE_PREFIX_outputSchemaHintPrompt}}",
        get_conversational_output_hint_section(output_schema),
    )

    return prompt


def get_user_settings_template(
    user_settings: PromptUserSettings | None,
) -> str:
    """Get the user settings template section.

    Args:
        user_settings: User profile information

    Returns:
        The filled-in user settings template if user_settings is provided, otherwise an empty string
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


def get_conversation_id_template(conversation_id: str | None) -> str:
    """Get the conversation ID prompt section.

    Args:
        conversation_id: The ID of the current conversation, if any

    Returns:
        The filled-in conversation ID template if conversation_id is provided, otherwise an empty string
    """
    if not conversation_id:
        return ""
    return _CONVERSATION_ID_TEMPLATE.format(conversation_id=conversation_id)


_OUTPUT_HINT_SECTION_PREFIX = """=====================================================================
STRUCTURED OUTPUT FOR THIS TURN
=====================================================================
At the end of your turn (when you decide to reply without calling a tool), a separate step will infer structured output fields for this turn with the following schema:

```json
"""

_OUTPUT_HINT_SECTION_SUFFIX = """
```

- The outputs are produced after your turn, by a separate step. You have no tool for them: do not look for one, and do not call some other tool in its place.
- Instructions anywhere in the Agent System Prompt about what an output field should contain apply to those outputs, not to your reply. You do not need to do anything with them while replying.
- Your reply is what the user reads. These outputs are internal — later steps in the surrounding process may read them to decide routing or follow-up actions — so respond naturally in conversation rather than mentioning these output fields or their values."""


def get_conversational_output_hint_section(
    output_schema: type[BaseModel] | None,
) -> str:
    """Return the system-prompt section describing the turn's output fields.

    Conversational agents fill their declared output fields in a separate call
    after the loop - this section informs the model of these fields and how to
    handle them when replying.

    Args:
        output_schema: The fields to describe, or None for no section.

    Returns:
        The rendered section, or an empty string when there is no schema.
    """
    if output_schema is None:
        return ""

    schema_json = json.dumps(output_schema.model_json_schema(), indent=2)
    return f"{_OUTPUT_HINT_SECTION_PREFIX}{schema_json}{_OUTPUT_HINT_SECTION_SUFFIX}"


def strip_conversational_output_hint_section(assembled_system_prompt: str) -> str:
    """Remove the informative output-fields section from an assembled system prompt.

    After the conversational agent loop, an additional step will instruct the LLM to
    call the `set_conversational_output` tool to record structured output fields for the turn.
    This final call should not include the output-fields section in the system-prompt, which is
    only relevant for describing these outputs to the central conversational agent loop.
    """
    start = assembled_system_prompt.find(_OUTPUT_HINT_SECTION_PREFIX)
    if start == -1:
        return assembled_system_prompt
    end = assembled_system_prompt.find(
        _OUTPUT_HINT_SECTION_SUFFIX, start + len(_OUTPUT_HINT_SECTION_PREFIX)
    )
    if end == -1:
        return assembled_system_prompt
    # Removes exactly what was substituted for the placeholder, so the result
    # matches a prompt built without an output schema character for character.
    return (
        assembled_system_prompt[:start]
        + assembled_system_prompt[end + len(_OUTPUT_HINT_SECTION_SUFFIX) :]
    )


_GENERATE_OUTPUT_INSTRUCTION = """The conversational response for this turn has already been delivered to the user. Call the `set_conversational_output` tool to record the structured output fields for the CURRENT TURN ONLY. These structured outputs may be read and used by later steps in the surrounding process for routing/processing.

This instruction is not part of the conversation. The turn you are recording is the user's most recent message (not a tool-result) before this instruction, together with every message after it.

Rules:
- For each field, use values inferred from this turn. Only use earlier turns as context for interpreting this turn; do not report fields from an earlier turn that do not apply for this one.
- For optional fields that are not yet relevant or determinable (e.g. context is still being gathered, or the topic hasn't surfaced yet), omit them entirely.
- For required fields that cannot yet be determined, provide a default placeholder. DO NOT fabricate, guess, or hallucinate meaningful values.
- Do not produce any text response, as this will not be seen by the user. Only call the tool."""


def get_generate_output_prompt() -> str:
    """Return the framework-internal generate-output instruction.

    Appended as a final user-message to the conversational structured-output
    node's LLM call.
    """
    return _GENERATE_OUTPUT_INSTRUCTION
