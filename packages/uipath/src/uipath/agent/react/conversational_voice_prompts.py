"""Conversational voice agent prompt generation logic."""

from datetime import datetime, timezone

from .conversational_prompts import PromptUserSettings, get_user_settings_template

_VOICE_SYSTEM_PROMPT_TEMPLATE = """You are {{VOICE_AGENT_PREFIX_agentName}}.
The current date is: {{VOICE_AGENT_PREFIX_currentDate}}.

=====================================================================
AGENT SYSTEM PROMPT
=====================================================================
{{VOICE_AGENT_PREFIX_systemPrompt}}

{{VOICE_AGENT_PREFIX_userSettingsPrompt}}

=====================================================================
TOOL USAGE RULES
=====================================================================
Use the end call tool to end the call when:
- The primary objective of the call has been fulfilled and the user confirms they have no further questions
- The user explicitly asks to end the call or says goodbye

"""


def get_voice_system_prompt(
    system_message: str,
    agent_name: str | None,
    user_settings: PromptUserSettings | None = None,
) -> str:
    """Build the full voice system prompt with agent name, date, and optional user context."""
    formatted_date = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")

    prompt = _VOICE_SYSTEM_PROMPT_TEMPLATE
    prompt = prompt.replace(
        "{{VOICE_AGENT_PREFIX_agentName}}",
        agent_name or "Voice Assistant",
    )
    prompt = prompt.replace(
        "{{VOICE_AGENT_PREFIX_currentDate}}",
        formatted_date,
    )
    prompt = prompt.replace(
        "{{VOICE_AGENT_PREFIX_systemPrompt}}",
        system_message,
    )
    prompt = prompt.replace(
        "{{VOICE_AGENT_PREFIX_userSettingsPrompt}}",
        get_user_settings_template(user_settings),
    )

    return prompt
