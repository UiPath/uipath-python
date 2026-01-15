"""Tests for conversational agent prompt generation."""

import json
import re
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from uipath.agent.react.conversational_prompts import (
    CitationType,
    PromptUserSettings,
    _get_citation_example_prompt,
    _get_citation_format_prompt,
    _get_citation_type,
    _get_user_settings_template,
    get_chat_system_prompt,
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
        """Current date in ISO 8601 format is included."""
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

        assert "2026-01-15T10:30Z" in prompt

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


class TestCitationType:
    """Tests for citation type determination."""

    @pytest.mark.parametrize(
        "model",
        [
            "claude-3-sonnet",
            "claude-3-opus",
            "claude-3-haiku",
            "gemini-pro",
            "llama-3",
            "mistral-large",
        ],
    )
    def test_citation_type_wrapped_for_non_gpt_models(self, model):
        """Non-GPT models get CitationType.WRAPPED."""
        citation_type = _get_citation_type(model)

        assert citation_type == CitationType.WRAPPED

    @pytest.mark.parametrize(
        "model",
        [
            "gpt-4",
            "gpt-4o",
            "gpt-4o-2024-11-20",
            "gpt-3.5-turbo",
            "GPT-4",  # Test case insensitivity
            "GPT-4O-MINI",
        ],
    )
    def test_citation_type_trailing_for_gpt_models(self, model):
        """GPT models get CitationType.TRAILING."""
        citation_type = _get_citation_type(model)

        assert citation_type == CitationType.TRAILING


class TestCitationFormatPrompt:
    """Tests for citation format in generated prompts."""

    def test_citation_format_wrapped_in_prompt(self):
        """Wrapped citation format appears in prompt for non-GPT models."""
        prompt = get_chat_system_prompt(
            model="claude-3-sonnet",
            system_message=SYSTEM_MESSAGE,
            agent_name="Test Agent",
            user_settings=None,
        )

        assert "<uip:cite sources='[...]'>factual claim here</uip:cite>" in prompt

    def test_citation_format_trailing_in_prompt(self):
        """Trailing citation format appears in prompt for GPT models."""
        prompt = get_chat_system_prompt(
            model="gpt-4o",
            system_message=SYSTEM_MESSAGE,
            agent_name="Test Agent",
            user_settings=None,
        )

        assert "factual claim here<uip:cite sources='[...]'></uip:cite>" in prompt

    def test_wrapped_citation_examples_in_prompt(self):
        """Wrapped citation examples appear for non-GPT models."""
        prompt = get_chat_system_prompt(
            model="claude-3-sonnet",
            system_message=SYSTEM_MESSAGE,
            agent_name="Test Agent",
            user_settings=None,
        )

        # Check wrapped example
        assert (
            '<uip:cite sources=\'[{"title":"Study","url":"https://example.com"}]\'>AI adoption is growing</uip:cite>'
            in prompt
        )
        # Should NOT contain trailing example pattern
        assert (
            'AI adoption is growing<uip:cite sources=\'[{"title":"Study","url":"https://example.com"}]\'></uip:cite>'
            not in prompt
        )

    def test_trailing_citation_examples_in_prompt(self):
        """Trailing citation examples appear for GPT models."""
        prompt = get_chat_system_prompt(
            model="gpt-4o",
            system_message=SYSTEM_MESSAGE,
            agent_name="Test Agent",
            user_settings=None,
        )

        # Check trailing example
        assert (
            'AI adoption is growing<uip:cite sources=\'[{"title":"Study","url":"https://example.com"}]\'></uip:cite>'
            in prompt
        )


class TestGetCitationFormatPrompt:
    """Tests for _get_citation_format_prompt helper."""

    def test_wrapped_format(self):
        """Returns wrapped format string."""
        result = _get_citation_format_prompt(CitationType.WRAPPED)
        assert "<uip:cite sources='[...]'>factual claim here</uip:cite>" in result

    def test_trailing_format(self):
        """Returns trailing format string."""
        result = _get_citation_format_prompt(CitationType.TRAILING)
        assert "factual claim here<uip:cite sources='[...]'></uip:cite>" in result

    def test_none_format(self):
        """Returns empty string for NONE type."""
        result = _get_citation_format_prompt(CitationType.NONE)
        assert result == ""


class TestGetCitationExamplePrompt:
    """Tests for _get_citation_example_prompt helper."""

    def test_wrapped_example(self):
        """Returns wrapped example string."""
        result = _get_citation_example_prompt(CitationType.WRAPPED)
        assert "EXAMPLES OF CORRECT USAGE:" in result
        assert "CRITICAL ERRORS TO AVOID:" in result
        assert (
            '<uip:cite sources=\'[{"title":"Study","url":"https://example.com"}]\'>AI adoption is growing</uip:cite>'
            in result
        )

    def test_trailing_example(self):
        """Returns trailing example string."""
        result = _get_citation_example_prompt(CitationType.TRAILING)
        assert "EXAMPLES OF CORRECT USAGE:" in result
        assert "CRITICAL ERRORS TO AVOID:" in result
        assert (
            'AI adoption is growing<uip:cite sources=\'[{"title":"Study","url":"https://example.com"}]\'></uip:cite>'
            in result
        )

    def test_none_example(self):
        """Returns empty string for NONE type."""
        result = _get_citation_example_prompt(CitationType.NONE)
        assert result == ""


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
    """Tests for _get_user_settings_template helper."""

    def test_none_returns_empty(self):
        """Returns empty string when user_settings is None."""
        result = _get_user_settings_template(None)
        assert result == ""

    def test_empty_settings_returns_empty(self):
        """Returns empty string when all fields are None."""
        settings = PromptUserSettings()
        result = _get_user_settings_template(settings)
        assert result == ""

    def test_partial_settings_includes_non_none_only(self):
        """Only includes non-None fields in JSON."""
        settings = PromptUserSettings(name="Test", email="test@example.com")
        result = _get_user_settings_template(settings)

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
        result = _get_user_settings_template(settings)

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
