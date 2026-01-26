"""Tests for LegacyLlmAsAJudgeEvaluator placeholder auto-addition.

Tests that missing {{ActualOutput}} and {{ExpectedOutput}} placeholders are
automatically added to prompts with XML tags for clear delimitation.
"""

from unittest.mock import patch

from uipath.eval.evaluators.legacy_llm_as_judge_evaluator import (
    LegacyLlmAsAJudgeEvaluator,
)


class TestLegacyLlmAsAJudgePlaceholderValidation:
    """Test suite for automatic placeholder addition in legacy LLM judge evaluators."""

    def test_both_placeholders_present_no_modification(self):
        """Test that prompts with both placeholders are not modified."""
        original_prompt = (
            "Evaluate the quality.\n"
            "Actual: {{ActualOutput}}\n"
            "Expected: {{ExpectedOutput}}"
        )

        with patch("uipath.platform.UiPath"):
            evaluator = LegacyLlmAsAJudgeEvaluator(
                id="test",
                category="AI",
                evaluator_type="LLMAsJudge",
                name="TestEvaluator",
                description="Test",
                created_at="2025-01-01T00:00:00Z",
                updated_at="2025-01-01T00:00:00Z",
                config={},
                prompt=original_prompt,
                model="gpt-4",
            )

        # Prompt should remain unchanged
        assert evaluator.prompt == original_prompt
        assert "## Actual Output" not in evaluator.prompt
        assert "## Expected Output" not in evaluator.prompt
        assert "<ActualOutput>" not in evaluator.prompt
        assert "<ExpectedOutput>" not in evaluator.prompt

    def test_missing_expected_output_placeholder_added_with_tags(self):
        """Test that missing {{ExpectedOutput}} is auto-added with XML tags."""
        original_prompt = "Evaluate this output: {{ActualOutput}}"

        with patch("uipath.platform.UiPath"):
            evaluator = LegacyLlmAsAJudgeEvaluator(
                id="test",
                category="AI",
                evaluator_type="LLMAsJudge",
                name="TestEvaluator",
                description="Test",
                created_at="2025-01-01T00:00:00Z",
                updated_at="2025-01-01T00:00:00Z",
                config={},
                prompt=original_prompt,
                model="gpt-4",
            )

        # Check that ExpectedOutput section was added
        assert "## Expected Output" in evaluator.prompt
        assert "<ExpectedOutput>" in evaluator.prompt
        assert "{{ExpectedOutput}}" in evaluator.prompt
        assert "</ExpectedOutput>" in evaluator.prompt

        # Original prompt should still be there
        assert "Evaluate this output: {{ActualOutput}}" in evaluator.prompt

        # Verify structure: tags should wrap the placeholder
        expected_section = (
            "\n\n## Expected Output\n"
            "<ExpectedOutput>\n"
            "{{ExpectedOutput}}\n"
            "</ExpectedOutput>"
        )
        assert expected_section in evaluator.prompt

    def test_missing_actual_output_placeholder_added_with_tags(self):
        """Test that missing {{ActualOutput}} is auto-added with XML tags."""
        original_prompt = "Compare against expected: {{ExpectedOutput}}"

        with patch("uipath.platform.UiPath"):
            evaluator = LegacyLlmAsAJudgeEvaluator(
                id="test",
                category="AI",
                evaluator_type="LLMAsJudge",
                name="TestEvaluator",
                description="Test",
                created_at="2025-01-01T00:00:00Z",
                updated_at="2025-01-01T00:00:00Z",
                config={},
                prompt=original_prompt,
                model="gpt-4",
            )

        # Check that ActualOutput section was added
        assert "## Actual Output" in evaluator.prompt
        assert "<ActualOutput>" in evaluator.prompt
        assert "{{ActualOutput}}" in evaluator.prompt
        assert "</ActualOutput>" in evaluator.prompt

        # Original prompt should still be there
        assert "Compare against expected: {{ExpectedOutput}}" in evaluator.prompt

        # Verify structure: tags should wrap the placeholder
        expected_section = (
            "\n\n## Actual Output\n<ActualOutput>\n{{ActualOutput}}\n</ActualOutput>"
        )
        assert expected_section in evaluator.prompt

    def test_both_placeholders_missing_both_added_with_tags(self):
        """Test that both placeholders are auto-added when both are missing."""
        original_prompt = "Evaluate the quality of the agent output."

        with patch("uipath.platform.UiPath"):
            evaluator = LegacyLlmAsAJudgeEvaluator(
                id="test",
                category="AI",
                evaluator_type="LLMAsJudge",
                name="TestEvaluator",
                description="Test",
                created_at="2025-01-01T00:00:00Z",
                updated_at="2025-01-01T00:00:00Z",
                config={},
                prompt=original_prompt,
                model="gpt-4",
            )

        # Check that both sections were added
        assert "## Actual Output" in evaluator.prompt
        assert "<ActualOutput>" in evaluator.prompt
        assert "{{ActualOutput}}" in evaluator.prompt
        assert "</ActualOutput>" in evaluator.prompt

        assert "## Expected Output" in evaluator.prompt
        assert "<ExpectedOutput>" in evaluator.prompt
        assert "{{ExpectedOutput}}" in evaluator.prompt
        assert "</ExpectedOutput>" in evaluator.prompt

        # Original prompt should still be there
        assert "Evaluate the quality of the agent output." in evaluator.prompt

        # Verify both sections are present
        actual_section = (
            "\n\n## Actual Output\n<ActualOutput>\n{{ActualOutput}}\n</ActualOutput>"
        )
        expected_section = (
            "\n\n## Expected Output\n"
            "<ExpectedOutput>\n"
            "{{ExpectedOutput}}\n"
            "</ExpectedOutput>"
        )
        assert actual_section in evaluator.prompt
        assert expected_section in evaluator.prompt

    def test_placeholder_order_actual_then_expected(self):
        """Test that when both placeholders are added, ActualOutput comes before ExpectedOutput."""
        original_prompt = "Rate the output quality."

        with patch("uipath.platform.UiPath"):
            evaluator = LegacyLlmAsAJudgeEvaluator(
                id="test",
                category="AI",
                evaluator_type="LLMAsJudge",
                name="TestEvaluator",
                description="Test",
                created_at="2025-01-01T00:00:00Z",
                updated_at="2025-01-01T00:00:00Z",
                config={},
                prompt=original_prompt,
                model="gpt-4",
            )

        # Find positions of the sections
        actual_pos = evaluator.prompt.find("## Actual Output")
        expected_pos = evaluator.prompt.find("## Expected Output")

        # ActualOutput should come before ExpectedOutput
        assert actual_pos < expected_pos

    def test_xml_tags_properly_nested(self):
        """Test that XML tags are properly nested around placeholders."""
        original_prompt = "Evaluate."

        with patch("uipath.platform.UiPath"):
            evaluator = LegacyLlmAsAJudgeEvaluator(
                id="test",
                category="AI",
                evaluator_type="LLMAsJudge",
                name="TestEvaluator",
                description="Test",
                created_at="2025-01-01T00:00:00Z",
                updated_at="2025-01-01T00:00:00Z",
                config={},
                prompt=original_prompt,
                model="gpt-4",
            )

        # Check proper nesting for ActualOutput
        actual_section = evaluator.prompt[evaluator.prompt.find("## Actual Output") :]
        assert "<ActualOutput>" in actual_section
        assert "{{ActualOutput}}" in actual_section
        assert "</ActualOutput>" in actual_section

        # Verify order: opening tag, placeholder, closing tag
        opening_tag_pos = actual_section.find("<ActualOutput>")
        placeholder_pos = actual_section.find("{{ActualOutput}}")
        closing_tag_pos = actual_section.find("</ActualOutput>")

        assert opening_tag_pos < placeholder_pos < closing_tag_pos

    def test_custom_placeholder_delimiters_not_affected(self):
        """Test that custom placeholder delimiters (curly braces) are preserved."""
        original_prompt = "Evaluate: {{ActualOutput}} vs {{ExpectedOutput}}"

        with patch("uipath.platform.UiPath"):
            evaluator = LegacyLlmAsAJudgeEvaluator(
                id="test",
                category="AI",
                evaluator_type="LLMAsJudge",
                name="TestEvaluator",
                description="Test",
                created_at="2025-01-01T00:00:00Z",
                updated_at="2025-01-01T00:00:00Z",
                config={},
                prompt=original_prompt,
                model="gpt-4",
            )

        # Double braces should be preserved
        assert "{{ActualOutput}}" in evaluator.prompt
        assert "{{ExpectedOutput}}" in evaluator.prompt
        # Single braces in tags should not interfere
        assert "<ActualOutput>" not in evaluator.prompt  # Shouldn't be added
        assert "<ExpectedOutput>" not in evaluator.prompt  # Shouldn't be added

    def test_sections_appended_not_prepended(self):
        """Test that missing sections are appended to the end, not prepended."""
        original_prompt = "Original prompt content at the start."

        with patch("uipath.platform.UiPath"):
            evaluator = LegacyLlmAsAJudgeEvaluator(
                id="test",
                category="AI",
                evaluator_type="LLMAsJudge",
                name="TestEvaluator",
                description="Test",
                created_at="2025-01-01T00:00:00Z",
                updated_at="2025-01-01T00:00:00Z",
                config={},
                prompt=original_prompt,
                model="gpt-4",
            )

        # Original prompt should be at the start
        assert evaluator.prompt.startswith("Original prompt content")
        # Added sections should be at the end
        assert evaluator.prompt.index("## Actual Output") > len(original_prompt)

    def test_multiline_prompt_with_missing_placeholders(self):
        """Test placeholder addition works with multiline prompts."""
        original_prompt = """
You are an expert evaluator.

Task: Evaluate the quality of the agent output.

Consider the following criteria:
1. Accuracy
2. Completeness
3. Clarity

Provide a score from 0-100.
"""

        with patch("uipath.platform.UiPath"):
            evaluator = LegacyLlmAsAJudgeEvaluator(
                id="test",
                category="AI",
                evaluator_type="LLMAsJudge",
                name="TestEvaluator",
                description="Test",
                created_at="2025-01-01T00:00:00Z",
                updated_at="2025-01-01T00:00:00Z",
                config={},
                prompt=original_prompt,
                model="gpt-4",
            )

        # Original multiline content should be preserved
        assert "You are an expert evaluator." in evaluator.prompt
        assert "1. Accuracy" in evaluator.prompt

        # Both placeholders should be added at the end
        assert "## Actual Output" in evaluator.prompt
        assert "## Expected Output" in evaluator.prompt
        assert evaluator.prompt.index("## Actual Output") > len(original_prompt)
