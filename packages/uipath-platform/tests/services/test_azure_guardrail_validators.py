"""Tests for the Azure-provided guardrail validators.

Covers HarmfulContentValidator, IntellectualPropertyValidator, and
UserPromptAttacksValidator — verifying guardrail construction, parameter
serialization, stage enforcement, and input validation.
"""

from __future__ import annotations

import pytest

from uipath.platform.guardrails.decorators import (
    GuardrailExecutionStage,
    HarmfulContentEntity,
    HarmfulContentEntityType,
    HarmfulContentValidator,
    IntellectualPropertyEntityType,
    IntellectualPropertyValidator,
    UserPromptAttacksValidator,
)

# ---------------------------------------------------------------------------
# HarmfulContentValidator
# ---------------------------------------------------------------------------


class TestHarmfulContentValidator:
    """Tests for HarmfulContentValidator."""

    def test_builds_guardrail(self):
        """Verify get_built_in_guardrail returns correct structure."""
        validator = HarmfulContentValidator(
            entities=[
                HarmfulContentEntity(HarmfulContentEntityType.VIOLENCE, threshold=3),
                HarmfulContentEntity(HarmfulContentEntityType.HATE, threshold=4),
            ]
        )
        guardrail = validator.get_built_in_guardrail(
            name="Test HC",
            description="test",
            enabled_for_evals=True,
        )
        assert guardrail.validator_type == "harmful_content"
        assert len(guardrail.validator_parameters) == 2

        enum_param = guardrail.validator_parameters[0]
        assert enum_param.id == "harmfulContentEntities"
        assert enum_param.value == ["Violence", "Hate"]

        map_param = guardrail.validator_parameters[1]
        assert map_param.id == "harmfulContentEntityThresholds"
        assert map_param.value == {"Violence": 3, "Hate": 4}

    def test_empty_entities_raises(self):
        """Empty entities should raise ValueError."""
        with pytest.raises(ValueError, match="non-empty"):
            HarmfulContentValidator(entities=[])

    def test_threshold_validation(self):
        """Threshold outside 0-6 should raise ValueError."""
        with pytest.raises(ValueError, match="between 0 and 6"):
            HarmfulContentEntity(HarmfulContentEntityType.VIOLENCE, threshold=7)
        with pytest.raises(ValueError, match="between 0 and 6"):
            HarmfulContentEntity(HarmfulContentEntityType.VIOLENCE, threshold=-1)

    def test_all_stages_supported(self):
        """supported_stages should be empty (all stages allowed)."""
        validator = HarmfulContentValidator(
            entities=[HarmfulContentEntity(HarmfulContentEntityType.VIOLENCE)]
        )
        assert validator.supported_stages == []
        # Should not raise for any stage
        validator.validate_stage(GuardrailExecutionStage.PRE)
        validator.validate_stage(GuardrailExecutionStage.POST)


# ---------------------------------------------------------------------------
# IntellectualPropertyValidator
# ---------------------------------------------------------------------------


class TestIntellectualPropertyValidator:
    """Tests for IntellectualPropertyValidator."""

    def test_builds_guardrail(self):
        """Verify get_built_in_guardrail returns correct structure."""
        validator = IntellectualPropertyValidator(
            entities=[
                IntellectualPropertyEntityType.TEXT,
                IntellectualPropertyEntityType.CODE,
            ]
        )
        guardrail = validator.get_built_in_guardrail(
            name="Test IP",
            description=None,
            enabled_for_evals=False,
        )
        assert guardrail.validator_type == "intellectual_property"
        assert len(guardrail.validator_parameters) == 1

        param = guardrail.validator_parameters[0]
        assert param.id == "ipEntities"
        assert param.value == ["Text", "Code"]

    def test_empty_entities_raises(self):
        """Empty entities should raise ValueError."""
        with pytest.raises(ValueError, match="non-empty"):
            IntellectualPropertyValidator(entities=[])

    def test_post_only(self):
        """Should only support POST stage."""
        validator = IntellectualPropertyValidator(
            entities=[IntellectualPropertyEntityType.TEXT]
        )
        assert validator.supported_stages == [GuardrailExecutionStage.POST]
        validator.validate_stage(GuardrailExecutionStage.POST)
        with pytest.raises(ValueError, match="does not support stage"):
            validator.validate_stage(GuardrailExecutionStage.PRE)


# ---------------------------------------------------------------------------
# UserPromptAttacksValidator
# ---------------------------------------------------------------------------


class TestUserPromptAttacksValidator:
    """Tests for UserPromptAttacksValidator."""

    def test_builds_guardrail(self):
        """Verify get_built_in_guardrail returns correct structure."""
        validator = UserPromptAttacksValidator()
        guardrail = validator.get_built_in_guardrail(
            name="Test UPA",
            description=None,
            enabled_for_evals=True,
        )
        assert guardrail.validator_type == "user_prompt_attacks"
        assert guardrail.validator_parameters == []

    def test_pre_only(self):
        """Should only support PRE stage."""
        validator = UserPromptAttacksValidator()
        assert validator.supported_stages == [GuardrailExecutionStage.PRE]
        validator.validate_stage(GuardrailExecutionStage.PRE)
        with pytest.raises(ValueError, match="does not support stage"):
            validator.validate_stage(GuardrailExecutionStage.POST)
