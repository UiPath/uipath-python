"""Tests for conversational agent prompt generation."""

import json
import re
from datetime import datetime, timezone
from unittest.mock import patch

from pydantic import BaseModel, Field

from uipath.agent.react.conversational_prompts import (
    PromptUserSettings,
    get_chat_system_prompt,
    get_conversational_output_hint_section,
    get_generate_output_prompt,
    get_user_settings_template,
    strip_conversational_output_hint_section,
)

SYSTEM_MESSAGE = "You are a helpful assistant."


class TestGenerateConversationalAgentSystemPrompt:
    """Tests for get_chat_system_prompt function."""

    def test_generate_system_prompt_basic(self):
        """Generate prompt with minimal inputs."""
        prompt = get_chat_system_prompt(
            model="claude-3-sonnet",
            system_message=SYSTEM_MESSAGE,
            agent_name="Basic Agent",
            user_settings=None,
        )

        assert "You are Basic Agent." in prompt
        assert "You are a helpful assistant." in prompt
        assert "AGENT SYSTEM PROMPT" in prompt
        assert "TOOL USAGE RULES" in prompt

    def test_generate_system_prompt_with_user_settings(self):
        """Prompt includes user context when PromptUserSettings provided."""
        user_settings = PromptUserSettings(
            name="John Doe",
            email="john.doe@example.com",
            role="Developer",
            department="Engineering",
            company="Acme Corp",
            country="USA",
            timezone="America/New_York",
        )

        prompt = get_chat_system_prompt(
            model="claude-3-sonnet",
            system_message=SYSTEM_MESSAGE,
            agent_name="Test Agent",
            user_settings=user_settings,
        )

        assert "USER CONTEXT" in prompt
        assert "John Doe" in prompt
        assert "john.doe@example.com" in prompt
        assert "Developer" in prompt
        assert "Engineering" in prompt
        assert "Acme Corp" in prompt
        assert "USA" in prompt
        assert "America/New_York" in prompt

    def test_generate_system_prompt_without_user_settings(self):
        """Prompt excludes user context section when user_settings=None."""
        prompt = get_chat_system_prompt(
            model="claude-3-sonnet",
            system_message=SYSTEM_MESSAGE,
            agent_name="Test Agent",
            user_settings=None,
        )

        assert "USER CONTEXT" not in prompt

    def test_generate_system_prompt_with_partial_user_settings(self):
        """Only non-None user settings fields are included in JSON."""
        user_settings = PromptUserSettings(
            name="Jane Doe",
            email="jane@example.com",
            # Other fields are None
        )

        prompt = get_chat_system_prompt(
            model="claude-3-sonnet",
            system_message=SYSTEM_MESSAGE,
            agent_name="Test Agent",
            user_settings=user_settings,
        )

        assert "USER CONTEXT" in prompt
        assert "Jane Doe" in prompt
        assert "jane@example.com" in prompt
        # None fields should not appear in the JSON
        assert '"role":' not in prompt
        assert '"department":' not in prompt

    def test_generate_system_prompt_includes_agent_name(self):
        """Agent name is substituted into prompt."""
        prompt = get_chat_system_prompt(
            model="claude-3-sonnet",
            system_message=SYSTEM_MESSAGE,
            agent_name="Customer Support Bot",
            user_settings=None,
        )

        assert "You are Customer Support Bot." in prompt

    def test_generate_system_prompt_includes_current_date(self):
        """Current date is included, truncated to the hour."""
        # Mock datetime to have a predictable value
        mock_dt = datetime(2026, 1, 15, 10, 30, tzinfo=timezone.utc)
        with patch(
            "uipath.agent.react.conversational_prompts.datetime"
        ) as mock_datetime:
            mock_datetime.now.return_value = mock_dt
            mock_datetime.side_effect = lambda *args, **kwargs: datetime(
                *args, **kwargs
            )

            prompt = get_chat_system_prompt(
                model="claude-3-sonnet",
                system_message=SYSTEM_MESSAGE,
                agent_name="Test Agent",
                user_settings=None,
            )

        assert "Thursday, January 15, 2026, 10:00 UTC" in prompt
        assert "10:30" not in prompt

    def test_generate_system_prompt_includes_attachments_section(self):
        """Attachments template is always included."""
        prompt = get_chat_system_prompt(
            model="claude-3-sonnet",
            system_message=SYSTEM_MESSAGE,
            agent_name="Test Agent",
            user_settings=None,
        )

        assert "ATTACHMENTS" in prompt
        assert "job attachments" in prompt.lower()
        assert "<uip:attachments>" in prompt

    def test_generate_system_prompt_unnamed_agent_uses_default(self):
        """Unnamed agent defaults to 'Unnamed Agent'."""
        prompt = get_chat_system_prompt(
            model="claude-3-sonnet",
            system_message=SYSTEM_MESSAGE,
            agent_name=None,
            user_settings=None,
        )

        assert "You are Unnamed Agent." in prompt


class TestConversationIdInPrompt:
    """Tests for conversation_id in generated prompts."""

    def test_prompt_includes_conversation_id_when_provided(self):
        prompt = get_chat_system_prompt(
            model="claude-3-sonnet",
            system_message=SYSTEM_MESSAGE,
            agent_name="Test Agent",
            user_settings=None,
            conversation_id="conv-abc-123",
        )

        assert "The current conversation ID is conv-abc-123" in prompt
        assert (
            "This may be useful to include in tool-calls when tool parameters specify passing in the conversation ID."
            in prompt
        )
        assert (
            "{{CONVERSATIONAL_AGENT_SERVICE_PREFIX_conversationIdPrompt}}" not in prompt
        )

    def test_prompt_omits_section_when_none(self):
        prompt = get_chat_system_prompt(
            model="claude-3-sonnet",
            system_message=SYSTEM_MESSAGE,
            agent_name="Test Agent",
            user_settings=None,
            conversation_id=None,
        )

        assert "conversation ID" not in prompt
        assert (
            "{{CONVERSATIONAL_AGENT_SERVICE_PREFIX_conversationIdPrompt}}" not in prompt
        )

    def test_prompt_omits_section_when_empty_string(self):
        prompt = get_chat_system_prompt(
            model="claude-3-sonnet",
            system_message=SYSTEM_MESSAGE,
            agent_name="Test Agent",
            user_settings=None,
            conversation_id="",
        )

        assert "conversation ID" not in prompt

    def test_prompt_defaults_to_no_conversation_id(self):
        """conversation_id defaults to None — call sites that don't pass it
        must not get a dangling placeholder."""
        prompt = get_chat_system_prompt(
            model="claude-3-sonnet",
            system_message=SYSTEM_MESSAGE,
            agent_name="Test Agent",
            user_settings=None,
        )

        assert (
            "{{CONVERSATIONAL_AGENT_SERVICE_PREFIX_conversationIdPrompt}}" not in prompt
        )
        assert "conversation ID" not in prompt


class TestCitationFormat:
    """Tests for citation format in generated prompts."""

    def test_citation_format_claude(self):
        prompt = get_chat_system_prompt(
            model="claude-3-sonnet",
            system_message=SYSTEM_MESSAGE,
            agent_name="Test Agent",
            user_settings=None,
        )

        assert (
            '<uip:cite title="Document Title" reference="https://url" page_number="1"/>'
            in prompt
        )

    def test_citation_format_gpt(self):
        prompt = get_chat_system_prompt(
            model="gpt-4o",
            system_message=SYSTEM_MESSAGE,
            agent_name="Test Agent",
            user_settings=None,
        )

        assert (
            '<uip:cite title="Document Title" reference="https://url" page_number="1"/>'
            in prompt
        )

    def test_citation_examples_in_prompt(self):
        prompt = get_chat_system_prompt(
            model="claude-3-sonnet",
            system_message=SYSTEM_MESSAGE,
            agent_name="Test Agent",
            user_settings=None,
        )

        assert "EXAMPLES OF CORRECT USAGE:" in prompt
        assert (
            '<uip:cite title="Industry Study" url="https://example.com/study"/>'
            in prompt
        )
        assert (
            '<uip:cite title="Policy Manual v2.pdf" reference="https://docs.example.com/ref" page_number="15"/>'
            in prompt
        )
        assert "CRITICAL ERRORS TO AVOID:" in prompt


class TestPromptUserSettings:
    """Tests for PromptUserSettings dataclass."""

    def test_all_fields_populated(self):
        """All fields populated in PromptUserSettings."""
        settings = PromptUserSettings(
            name="Test User",
            email="test@example.com",
            role="Admin",
            department="IT",
            company="Test Co",
            country="Canada",
            timezone="America/Toronto",
        )

        assert settings.name == "Test User"
        assert settings.email == "test@example.com"
        assert settings.role == "Admin"
        assert settings.department == "IT"
        assert settings.company == "Test Co"
        assert settings.country == "Canada"
        assert settings.timezone == "America/Toronto"

    def test_default_none_values(self):
        """Default values are None."""
        settings = PromptUserSettings()

        assert settings.name is None
        assert settings.email is None
        assert settings.role is None
        assert settings.department is None
        assert settings.company is None
        assert settings.country is None
        assert settings.timezone is None


class TestGetUserSettingsTemplate:
    """Tests for get_user_settings_template helper."""

    def test_none_returns_empty(self):
        """Returns empty string when user_settings is None."""
        result = get_user_settings_template(None)
        assert result == ""

    def test_empty_settings_returns_empty(self):
        """Returns empty string when all fields are None."""
        settings = PromptUserSettings()
        result = get_user_settings_template(settings)
        assert result == ""

    def test_partial_settings_includes_non_none_only(self):
        """Only includes non-None fields in JSON."""
        settings = PromptUserSettings(name="Test", email="test@example.com")
        result = get_user_settings_template(settings)

        assert "USER CONTEXT" in result
        assert '"name": "Test"' in result or '"name":"Test"' in result
        assert "test@example.com" in result
        # None fields should not be present
        assert "role" not in result
        assert "department" not in result

    def test_full_settings_json_format(self):
        """Full settings are formatted as valid JSON."""
        settings = PromptUserSettings(
            name="Full User",
            email="full@example.com",
            role="Manager",
            department="Sales",
            company="Big Corp",
            country="UK",
            timezone="Europe/London",
        )
        result = get_user_settings_template(settings)

        # Extract JSON from the result
        json_match = re.search(r"```json\s*(\{[^`]+\})\s*```", result)
        assert json_match is not None

        # Validate it's proper JSON
        json_data = json.loads(json_match.group(1))
        assert json_data["name"] == "Full User"
        assert json_data["email"] == "full@example.com"
        assert json_data["role"] == "Manager"
        assert json_data["department"] == "Sales"
        assert json_data["company"] == "Big Corp"
        assert json_data["country"] == "UK"
        assert json_data["timezone"] == "Europe/London"


class TestGetGenerateOutputPrompt:
    """Tests for get_generate_output_prompt function."""

    def test_returns_non_empty_string(self):
        instruction = get_generate_output_prompt()
        assert isinstance(instruction, str)
        assert instruction.strip()

    def test_references_set_conversational_output_tool(self):
        """The instruction must name the tool the new node binds."""
        assert "set_conversational_output" in get_generate_output_prompt()

    def test_scopes_the_record_to_the_current_turn(self):
        """A flow can loop back to this agent, so re-reporting an earlier
        turn's field would re-trigger whatever consumes it."""
        assert "CURRENT TURN ONLY" in get_generate_output_prompt()

    def test_excludes_itself_from_the_conversation(self):
        """It is appended as a user message, so an unqualified "latest user
        message" would anchor on this instruction. Tool results also arrive as
        user-role content on Anthropic and Gemini, hence the second clause."""
        instruction = _flat(get_generate_output_prompt())

        assert "This instruction is not part of the conversation." in instruction
        assert "(not a tool-result)" in instruction


class _OutputFields(BaseModel):
    """The fields the model fills, as the caller narrows them before passing."""

    status: str = Field(description="Set to 'resolved' once the user confirms.")
    escalated: bool = False


def _flat(text: str) -> str:
    """Collapse hard wrapping so assertions survive the prompt being rewrapped."""
    return " ".join(text.split())


def _prompt(**kwargs):
    return get_chat_system_prompt(
        model="claude-3-sonnet",
        system_message=SYSTEM_MESSAGE,
        agent_name="Agent",
        **kwargs,
    )


class TestGetConversationalOutputHintSection:
    """Tests for get_conversational_output_hint_section."""

    def test_empty_without_a_schema(self):
        """None means no section, matching get_user_settings_template and
        get_conversation_id_template, so callers pass their optional through."""
        assert get_conversational_output_hint_section(None) == ""

    def test_renders_the_schema_as_json(self):
        """Rendered verbatim, so new JSON-Schema features need no change here:
        enums, nested objects, constraints and examples all ride along."""
        section = get_conversational_output_hint_section(_OutputFields)

        assert "```json" in section
        payload = json.loads(section.split("```json")[1].split("```")[0])

        assert payload == _OutputFields.model_json_schema()
        assert (
            payload["properties"]["status"]["description"]
            == "Set to 'resolved' once the user confirms."
        )

    def test_describes_whatever_it_is_given(self):
        """Narrowing is the caller's job: this module has no notion of
        framework-managed fields and describes every field it receives."""

        class _WithFrameworkField(BaseModel):
            uipath__agent_response_messages: list[str] = Field(default_factory=list)

        assert "uipath__agent_response_messages" in (
            get_conversational_output_hint_section(_WithFrameworkField)
        )

    def test_tells_the_loop_it_has_no_tool_for_the_fields(self):
        """The reported bug: the agent hunts for a tool that does not exist."""
        assert "no tool for them" in _flat(
            get_conversational_output_hint_section(_OutputFields)
        )


class TestOutputHintSectionInSystemPrompt:
    """The section reaches the assembled prompt via its own placeholder."""

    def test_absent_by_default(self):
        assert "STRUCTURED OUTPUT FOR THIS TURN" not in _prompt()

    def test_present_with_output_fields(self):
        prompt = _prompt(output_schema=_OutputFields)

        assert "STRUCTURED OUTPUT FOR THIS TURN" in prompt
        assert '"status"' in prompt

    def test_placeholder_is_always_consumed(self):
        for prompt in (_prompt(), _prompt(output_schema=_OutputFields)):
            assert "CONVERSATIONAL_AGENT_SERVICE_PREFIX_outputSchemaHintPrompt" not in (
                prompt
            )

    def test_keeps_the_rest_of_the_prompt(self):
        prompt = _prompt(output_schema=_OutputFields)

        assert "You are Agent." in prompt
        assert SYSTEM_MESSAGE in prompt
        assert "TOOL USAGE RULES" in prompt


class TestStripConversationalOutputHintSection:
    """The structured-output call must not inherit the loop-only section.

    It says the agent has no tool for these fields, and the prompt's own
    precedence hierarchy ranks the system prompt above the user message that
    carries the instruction to call exactly that tool. Forced tool choice hides
    the conflict today; a model that cannot be forced would resolve it wrongly.
    """

    def test_restores_the_prompt_exactly(self):
        """Byte-for-byte, so no stray blank lines are left behind."""
        assert (
            strip_conversational_output_hint_section(
                _prompt(output_schema=_OutputFields)
            )
            == _prompt()
        )

    def test_removes_the_contradiction(self):
        stripped = strip_conversational_output_hint_section(
            _prompt(output_schema=_OutputFields)
        )

        assert "no tool for them" not in _flat(stripped)

    def test_no_op_when_the_section_is_absent(self):
        assert strip_conversational_output_hint_section(_prompt()) == _prompt()

    def test_is_idempotent(self):
        once = strip_conversational_output_hint_section(
            _prompt(output_schema=_OutputFields)
        )

        assert strip_conversational_output_hint_section(once) == once

    def test_survives_text_appended_after_the_section(self):
        """Advanced agents append a meta prompt after the assembled prompt."""
        prompt = _prompt(output_schema=_OutputFields) + "\n\nEXTRA META PROMPT"

        stripped = strip_conversational_output_hint_section(prompt)

        assert "STRUCTURED OUTPUT FOR THIS TURN" not in stripped
        assert stripped.endswith("EXTRA META PROMPT")

    def test_strips_a_section_built_from_a_different_field_list(self):
        """It takes no schema, so it cannot drift from however the caller
        narrowed one — an earlier version re-rendered the section to find it
        and silently did nothing on a mismatch."""

        class _Other(BaseModel):
            wholly_different: int = Field(description="Nothing like the above.")

        stripped = strip_conversational_output_hint_section(
            _prompt(output_schema=_Other)
        )

        assert "wholly_different" not in stripped
        assert stripped == _prompt()
