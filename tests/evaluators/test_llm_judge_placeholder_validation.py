"""Tests for LLMJudgeMixin placeholder auto-addition.

Tests that missing {{ActualOutput}} and {{ExpectedOutput}} placeholders are
automatically added to prompts with XML tags for clear delimitation.
"""

import uuid
from unittest.mock import patch

from uipath.eval.evaluators.llm_judge_output_evaluator import (
    LLMJudgeOutputEvaluator,
)


class TestLLMJudgePlaceholderValidation:
    """Test suite for automatic placeholder addition in LLM judge evaluators."""

    def test_both_placeholders_present_no_modification(self):
        """Test that prompts with both placeholders are not modified."""
        original_prompt = (
            "Evaluate the quality.\n"
            "Actual: {{ActualOutput}}\n"
            "Expected: {{ExpectedOutput}}"
        )

        config = {
            "name": "TestEvaluator",
            "prompt": original_prompt,
            "model": "gpt-4",
        }

        with patch("uipath.platform.UiPath"):
            evaluator = LLMJudgeOutputEvaluator.model_validate(
                {"config": config, "id": str(uuid.uuid4())}
            )

        # Prompt should remain unchanged
        assert evaluator.evaluator_config.prompt == original_prompt
        assert "## Actual Output" not in evaluator.evaluator_config.prompt
        assert "## Expected Output" not in evaluator.evaluator_config.prompt
        assert "<ActualOutput>" not in evaluator.evaluator_config.prompt
        assert "<ExpectedOutput>" not in evaluator.evaluator_config.prompt

    def test_missing_expected_output_placeholder_added_with_tags(self):
        """Test that missing {{ExpectedOutput}} is auto-added with XML tags."""
        original_prompt = "Evaluate this output: {{ActualOutput}}"

        config = {
            "name": "TestEvaluator",
            "prompt": original_prompt,
            "model": "gpt-4",
        }

        with patch("uipath.platform.UiPath"):
            evaluator = LLMJudgeOutputEvaluator.model_validate(
                {"config": config, "id": str(uuid.uuid4())}
            )

        # Check that ExpectedOutput section was added
        assert "## Expected Output" in evaluator.evaluator_config.prompt
        assert "<ExpectedOutput>" in evaluator.evaluator_config.prompt
        assert "{{ExpectedOutput}}" in evaluator.evaluator_config.prompt
        assert "</ExpectedOutput>" in evaluator.evaluator_config.prompt

        # Original prompt should still be there
        assert (
            "Evaluate this output: {{ActualOutput}}"
            in evaluator.evaluator_config.prompt
        )

        # Verify structure: tags should wrap the placeholder
        expected_section = (
            "\n\n## Expected Output\n"
            "<ExpectedOutput>\n"
            "{{ExpectedOutput}}\n"
            "</ExpectedOutput>"
        )
        assert expected_section in evaluator.evaluator_config.prompt

    def test_missing_actual_output_placeholder_added_with_tags(self):
        """Test that missing {{ActualOutput}} is auto-added with XML tags."""
        original_prompt = "Compare against expected: {{ExpectedOutput}}"

        config = {
            "name": "TestEvaluator",
            "prompt": original_prompt,
            "model": "gpt-4",
        }

        with patch("uipath.platform.UiPath"):
            evaluator = LLMJudgeOutputEvaluator.model_validate(
                {"config": config, "id": str(uuid.uuid4())}
            )

        # Check that ActualOutput section was added
        assert "## Actual Output" in evaluator.evaluator_config.prompt
        assert "<ActualOutput>" in evaluator.evaluator_config.prompt
        assert "{{ActualOutput}}" in evaluator.evaluator_config.prompt
        assert "</ActualOutput>" in evaluator.evaluator_config.prompt

        # Original prompt should still be there
        assert (
            "Compare against expected: {{ExpectedOutput}}"
            in evaluator.evaluator_config.prompt
        )

        # Verify structure: tags should wrap the placeholder
        expected_section = (
            "\n\n## Actual Output\n<ActualOutput>\n{{ActualOutput}}\n</ActualOutput>"
        )
        assert expected_section in evaluator.evaluator_config.prompt

    def test_both_placeholders_missing_both_added_with_tags(self):
        """Test that both placeholders are auto-added when both are missing."""
        original_prompt = "Evaluate the quality of the agent output."

        config = {
            "name": "TestEvaluator",
            "prompt": original_prompt,
            "model": "gpt-4",
        }

        with patch("uipath.platform.UiPath"):
            evaluator = LLMJudgeOutputEvaluator.model_validate(
                {"config": config, "id": str(uuid.uuid4())}
            )

        # Check that both sections were added
        assert "## Actual Output" in evaluator.evaluator_config.prompt
        assert "<ActualOutput>" in evaluator.evaluator_config.prompt
        assert "{{ActualOutput}}" in evaluator.evaluator_config.prompt
        assert "</ActualOutput>" in evaluator.evaluator_config.prompt

        assert "## Expected Output" in evaluator.evaluator_config.prompt
        assert "<ExpectedOutput>" in evaluator.evaluator_config.prompt
        assert "{{ExpectedOutput}}" in evaluator.evaluator_config.prompt
        assert "</ExpectedOutput>" in evaluator.evaluator_config.prompt

        # Original prompt should still be there
        assert (
            "Evaluate the quality of the agent output."
            in evaluator.evaluator_config.prompt
        )

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
        assert actual_section in evaluator.evaluator_config.prompt
        assert expected_section in evaluator.evaluator_config.prompt

    def test_placeholder_order_actual_then_expected(self):
        """Test that when both placeholders are added, ActualOutput comes before ExpectedOutput."""
        original_prompt = "Rate the output quality."

        config = {
            "name": "TestEvaluator",
            "prompt": original_prompt,
            "model": "gpt-4",
        }

        with patch("uipath.platform.UiPath"):
            evaluator = LLMJudgeOutputEvaluator.model_validate(
                {"config": config, "id": str(uuid.uuid4())}
            )

        # Find positions of the sections
        actual_pos = evaluator.evaluator_config.prompt.find("## Actual Output")
        expected_pos = evaluator.evaluator_config.prompt.find("## Expected Output")

        # ActualOutput should come before ExpectedOutput
        assert actual_pos < expected_pos

    def test_xml_tags_properly_nested(self):
        """Test that XML tags are properly nested around placeholders."""
        original_prompt = "Evaluate."

        config = {
            "name": "TestEvaluator",
            "prompt": original_prompt,
            "model": "gpt-4",
        }

        with patch("uipath.platform.UiPath"):
            evaluator = LLMJudgeOutputEvaluator.model_validate(
                {"config": config, "id": str(uuid.uuid4())}
            )

        # Check proper nesting for ActualOutput
        actual_section = evaluator.evaluator_config.prompt[
            evaluator.evaluator_config.prompt.find("## Actual Output") :
        ]
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

        config = {
            "name": "TestEvaluator",
            "prompt": original_prompt,
            "model": "gpt-4",
        }

        with patch("uipath.platform.UiPath"):
            evaluator = LLMJudgeOutputEvaluator.model_validate(
                {"config": config, "id": str(uuid.uuid4())}
            )

        # Double braces should be preserved
        assert "{{ActualOutput}}" in evaluator.evaluator_config.prompt
        assert "{{ExpectedOutput}}" in evaluator.evaluator_config.prompt
        # Single braces in tags should not interfere
        assert (
            "<ActualOutput>" not in evaluator.evaluator_config.prompt
        )  # Shouldn't be added
        assert (
            "<ExpectedOutput>" not in evaluator.evaluator_config.prompt
        )  # Shouldn't be added

    def test_sections_appended_not_prepended(self):
        """Test that missing sections are appended to the end, not prepended."""
        original_prompt = "Original prompt content at the start."

        config = {
            "name": "TestEvaluator",
            "prompt": original_prompt,
            "model": "gpt-4",
        }

        with patch("uipath.platform.UiPath"):
            evaluator = LLMJudgeOutputEvaluator.model_validate(
                {"config": config, "id": str(uuid.uuid4())}
            )

        # Original prompt should be at the start
        assert evaluator.evaluator_config.prompt.startswith("Original prompt content")
        # Added sections should be at the end
        assert evaluator.evaluator_config.prompt.index("## Actual Output") > len(
            original_prompt
        )

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

        config = {
            "name": "TestEvaluator",
            "prompt": original_prompt,
            "model": "gpt-4",
        }

        with patch("uipath.platform.UiPath"):
            evaluator = LLMJudgeOutputEvaluator.model_validate(
                {"config": config, "id": str(uuid.uuid4())}
            )

        # Original multiline content should be preserved
        assert "You are an expert evaluator." in evaluator.evaluator_config.prompt
        assert "1. Accuracy" in evaluator.evaluator_config.prompt

        # Both placeholders should be added at the end
        assert "## Actual Output" in evaluator.evaluator_config.prompt
        assert "## Expected Output" in evaluator.evaluator_config.prompt
        assert evaluator.evaluator_config.prompt.index("## Actual Output") > len(
            original_prompt
        )
