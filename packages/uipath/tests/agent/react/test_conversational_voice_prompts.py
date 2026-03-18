"""Tests for voice agent prompt generation."""

from uipath.agent.react import PromptUserSettings, get_voice_system_prompt


class TestGetVoiceSystemPrompt:
    """Test get_voice_system_prompt with various user settings."""

    def test_no_user_settings(self) -> None:
        result = get_voice_system_prompt("Be helpful.", "Agent")
        assert "USER CONTEXT" not in result
        assert "Be helpful." in result

    def test_with_user_settings(self) -> None:
        settings = PromptUserSettings(name="Alice", email="alice@test.com")
        result = get_voice_system_prompt("Be helpful.", "Agent", user_settings=settings)
        assert "USER CONTEXT" in result
        assert '"name": "Alice"' in result
        assert '"email": "alice@test.com"' in result

    def test_user_settings_none_values_excluded(self) -> None:
        settings = PromptUserSettings(name="Bob")
        result = get_voice_system_prompt("Be helpful.", "Agent", user_settings=settings)
        assert '"name": "Bob"' in result
        assert "email" not in result

    def test_user_settings_all_none_skipped(self) -> None:
        settings = PromptUserSettings()
        result = get_voice_system_prompt("Be helpful.", "Agent", user_settings=settings)
        assert "USER CONTEXT" not in result

    def test_default_agent_name(self) -> None:
        result = get_voice_system_prompt("Hello.", None)
        assert "You are Voice Assistant." in result

    def test_includes_date_and_system_message(self) -> None:
        result = get_voice_system_prompt("Do things.", "MyAgent")
        assert "You are MyAgent." in result
        assert "The current date is:" in result
        assert "Do things." in result
