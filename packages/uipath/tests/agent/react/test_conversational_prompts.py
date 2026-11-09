"""Tests for conversational agent prompt generation."""

import json
import re
from datetime import datetime, timezone
from unittest.mock import patch

from pydantic import BaseModel, Field

from uipath.agent.react.conversational_prompts import (
    PromptUserSettings,
    get_chat_system_prompt,
    get_conversational_output_section,
    get_generate_output_prompt,
    get_user_settings_template,
    strip_conversational_output_section,
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


class _OutputSchema(BaseModel):
    """The fields the model fills, as the caller narrows them before passing."""

    status: str = Field(description="Set to 'resolved' once the user confirms.")
    ticket_id: str | None = Field(
        default=None, description="The raised ticket, if any."
    )
    escalated: bool = False


class TestGetConversationalOutputSection:
    """Tests for get_conversational_output_section."""

    def test_empty_without_a_schema(self):
        """None means no section, matching get_user_settings_template and
        get_conversation_id_template, so the caller can pass its optional
        straight through."""
        assert get_conversational_output_section(None) == ""

    def test_renders_the_schema_as_json(self):
        """The schema goes in verbatim, so new JSON-Schema features need no
        change here: enums, nested objects, constraints and examples all ride
        along."""
        section = get_conversational_output_section(_OutputSchema)

        assert "```json" in section
        payload = json.loads(section.split("```json")[1].split("```")[0])

        assert payload == _OutputSchema.model_json_schema()
        assert set(payload["properties"]) == {"status", "ticket_id", "escalated"}
        assert payload["required"] == ["status"]
        assert (
            payload["properties"]["status"]["description"]
            == "Set to 'resolved' once the user confirms."
        )

    def test_describes_whatever_it_is_given(self):
        """Narrowing is the caller's job, not this module's.

        It has no notion of framework-managed fields; callers pass only the
        fields the model should fill (uipath-langchain narrows with
        build_conversational_output_args_schema first).
        """

        class _WithFrameworkField(BaseModel):
            uipath__agent_response_messages: list[str] = Field(default_factory=list)

        section = get_conversational_output_section(_WithFrameworkField)

        assert "uipath__agent_response_messages" in section

    def test_tells_the_agent_there_is_no_tool_for_them(self):
        """The reported bug: the agent hunts for a tool that does not exist."""
        section = get_conversational_output_section(_OutputSchema).lower()
        assert "no tool" in section

    def test_redirects_prompt_guidance_to_the_record(self):
        """Builders write output guidance in the system prompt; it must land somewhere."""
        assert "not to your reply" in get_conversational_output_section(_OutputSchema)

    def test_forbids_mentioning_the_fields_to_the_user(self):
        """Seeing the fields invites narrating them; replies must stay conversational."""
        section = " ".join(get_conversational_output_section(_OutputSchema).split())

        assert "Respond naturally in conversation rather than mentioning" in section

    def test_is_stable_across_calls(self):
        assert get_conversational_output_section(
            _OutputSchema
        ) == get_conversational_output_section(_OutputSchema)


class TestTurnScoping:
    """Both prompts must agree on what "this turn" means, and on its scope.

    The history is [system, user, AI(tools)..., AI(no tools), user, ...], so a
    turn is one user message plus the agent's work up to its tool-less reply.
    Each turn is recorded separately and the record is consumed downstream, so
    repeating an earlier turn's value would re-fire whatever it triggers when a
    flow loops back to this agent.
    """

    @staticmethod
    def _flat(text: str) -> str:
        """Collapse the prompt's hard wrapping so assertions survive rewrapping."""
        return " ".join(text.split())

    def _section(self) -> str:
        class _Fields(BaseModel):
            status: str = ""

        return self._flat(get_conversational_output_section(_Fields))

    def test_loop_section_defines_the_turn_end_by_the_agent_s_own_action(self):
        """Models have no native notion of a multi-message turn, so the end is
        pinned to something observable at decision time — "when you reply
        without calling a tool" — rather than to a span of the transcript."""
        section = self._section()

        assert "At the end of your turn" in section
        assert "when you decide to reply without calling a tool" in section

    def test_loop_section_leaves_turn_scoping_to_the_extraction_step(self):
        """The loop only has to not record anything; the extraction step does the
        scoping, so those rules live there rather than being restated here."""
        section = self._section()

        assert "You have no tool for them" in section
        assert "CURRENT TURN ONLY" not in section

    def test_extraction_prompt_excludes_itself_from_the_conversation(self):
        """It is appended as a user message, so an unqualified "latest user
        message" would point at this instruction rather than the user's."""
        instruction = self._flat(get_generate_output_prompt())

        assert "This instruction is not part of the conversation." in instruction
        assert "before this instruction" in instruction
        assert "every message after it" in instruction

    def test_extraction_prompt_anchors_on_a_real_user_message(self):
        """Tool results reach the model as user-role content on some providers,
        so the anchor has to exclude them explicitly."""
        assert "(not a tool-result)" in get_generate_output_prompt()

    def test_extraction_prompt_treats_earlier_turns_as_context_only(self):
        """Not carry-forward: a flow can loop back to this agent, and repeating
        an earlier turn's field would re-trigger whatever consumes it."""
        instruction = self._flat(get_generate_output_prompt())

        assert "CURRENT TURN ONLY" in instruction
        assert "Only use earlier turns as context" in instruction
        assert "do not report fields from an earlier turn" in instruction


class TestOutputSectionInSystemPrompt:
    def _prompt(self, **kwargs):
        return get_chat_system_prompt(
            model="claude-3-sonnet",
            system_message=SYSTEM_MESSAGE,
            agent_name="Agent",
            **kwargs,
        )

    def test_absent_by_default(self):
        assert "STRUCTURED OUTPUT FOR THIS TURN" not in self._prompt()

    def test_present_with_output_fields(self):
        prompt = self._prompt(output_schema=_OutputSchema)

        assert "STRUCTURED OUTPUT FOR THIS TURN" in prompt
        assert '"status"' in prompt

    def test_keeps_the_rest_of_the_prompt(self):
        prompt = self._prompt(output_schema=_OutputSchema)

        assert "You are Agent." in prompt
        assert SYSTEM_MESSAGE in prompt
        assert "TOOL USAGE RULES" in prompt


class TestStripConversationalOutputSection:
    """The structured-output call must not inherit the loop-only section.

    It says the agent has no tool for these fields, and the prompt's own
    precedence hierarchy ranks the system prompt above the user message that
    carries the instruction to call exactly that tool. Forced tool choice hides
    the conflict today; a model that cannot be forced would resolve it wrongly.
    """

    def _prompt(self, **kwargs):
        return get_chat_system_prompt(
            model="claude-3-sonnet",
            system_message=SYSTEM_MESSAGE,
            agent_name="Agent",
            **kwargs,
        )

    def test_restores_the_prompt_exactly(self):
        """No trailing blank lines left behind."""
        assert (
            strip_conversational_output_section(
                self._prompt(output_schema=_OutputSchema)
            )
            == self._prompt()
        )

    def test_removes_the_contradiction(self):
        stripped = strip_conversational_output_section(
            self._prompt(output_schema=_OutputSchema)
        )

        assert "no tool for it" not in stripped

    def test_is_idempotent(self):
        once = strip_conversational_output_section(
            self._prompt(output_schema=_OutputSchema)
        )

        assert strip_conversational_output_section(once) == once

    def test_no_op_when_the_section_is_absent(self):
        prompt = self._prompt()

        assert strip_conversational_output_section(prompt) == prompt

    def test_survives_text_appended_after_the_section(self):
        """Advanced agents append a meta prompt after the assembled prompt."""
        prompt = self._prompt(output_schema=_OutputSchema) + "\n\nEXTRA META PROMPT"

        stripped = strip_conversational_output_section(prompt)

        assert "STRUCTURED OUTPUT FOR THIS TURN" not in stripped
        assert stripped.endswith("EXTRA META PROMPT")

    def test_strips_a_section_built_from_a_different_field_list(self):
        """Needs no schema, so it cannot drift from however the caller narrowed."""

        class _Other(BaseModel):
            wholly_different: int = Field(description="Nothing like the above.")

        stripped = strip_conversational_output_section(
            self._prompt(output_schema=_Other)
        )

        assert "wholly_different" not in stripped
        assert stripped == self._prompt()
