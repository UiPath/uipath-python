"""Tests for LLMAsJudgeValidator — the decorator-path llm_as_judge validator.

Verifies guardrail construction (validator_type + parameters), the
examples-only-when-present behavior, selector-is-None convention, stage support,
and input validation. Pure construction — no network.
"""

from __future__ import annotations

import pytest

from uipath.platform.guardrails.decorators import (
    GuardrailExecutionStage,
    LLMAsJudgeValidator,
)

_RULE = "The answer must be genuinely funny, clean, and on-topic."


class TestLLMAsJudgeValidator:
    """Tests for LLMAsJudgeValidator."""

    def test_builds_guardrail_type(self):
        guardrail = LLMAsJudgeValidator(
            guardrail_text=_RULE, model="gpt-4o-2024-08-06"
        ).get_built_in_guardrail(name="Judge", description=None, enabled_for_evals=True)
        assert guardrail.guardrail_type == "builtInValidator"
        assert guardrail.validator_type == "llm_as_judge"

    def test_required_parameters(self):
        guardrail = LLMAsJudgeValidator(
            guardrail_text=_RULE, model="gpt-4o-2024-08-06", threshold=2.0
        ).get_built_in_guardrail("Judge", None, True)
        params = {p.id: p for p in guardrail.validator_parameters}
        assert params["guardrailText"].parameter_type == "text"
        assert params["guardrailText"].value == _RULE
        assert params["model"].parameter_type == "enum"
        assert params["model"].value == "gpt-4o-2024-08-06"
        assert params["threshold"].parameter_type == "number"
        assert params["threshold"].value == 2.0

    def test_examples_only_when_present(self):
        ids = {
            p.id
            for p in LLMAsJudgeValidator(guardrail_text=_RULE, model="m")
            .get_built_in_guardrail("Judge", None, True)
            .validator_parameters
        }
        assert "positiveExamples" not in ids
        assert "negativeExamples" not in ids

        params = {
            p.id: p
            for p in LLMAsJudgeValidator(
                guardrail_text=_RULE,
                model="m",
                positive_examples=["a clean pun"],
                negative_examples=["not a joke"],
            )
            .get_built_in_guardrail("Judge", None, True)
            .validator_parameters
        }
        assert params["positiveExamples"].parameter_type == "text-list"
        assert params["positiveExamples"].value == ["a clean pun"]
        assert params["negativeExamples"].value == ["not a joke"]

    def test_selector_is_none(self):
        # Decorator-path convention (matches PIIValidator / PromptInjectionValidator):
        # scope comes from the decorated target, not the validator.
        guardrail = LLMAsJudgeValidator(
            guardrail_text=_RULE, model="m"
        ).get_built_in_guardrail("Judge", None, True)
        assert guardrail.selector is None

    def test_default_description(self):
        guardrail = LLMAsJudgeValidator(
            guardrail_text=_RULE, model="m"
        ).get_built_in_guardrail("Judge", None, True)
        assert guardrail.description == "LLM-as-judge evaluation"

    def test_all_stages_supported(self):
        validator = LLMAsJudgeValidator(guardrail_text=_RULE, model="m")
        assert validator.supported_stages == []
        # No stage restriction: both PRE and POST validate without raising.
        validator.validate_stage(GuardrailExecutionStage.PRE)
        validator.validate_stage(GuardrailExecutionStage.POST)

    def test_empty_guardrail_text_raises(self):
        with pytest.raises(ValueError, match="guardrail_text"):
            LLMAsJudgeValidator(guardrail_text="  ", model="m")

    def test_empty_model_raises(self):
        with pytest.raises(ValueError, match="model"):
            LLMAsJudgeValidator(guardrail_text=_RULE, model="")

    def test_threshold_out_of_range_raises(self):
        with pytest.raises(ValueError, match="threshold"):
            LLMAsJudgeValidator(guardrail_text=_RULE, model="m", threshold=7.0)

    def test_guardrail_text_over_limit_raises(self):
        with pytest.raises(ValueError, match="guardrail_text exceeds"):
            LLMAsJudgeValidator(guardrail_text="x" * 4001, model="m")

    def test_guardrail_text_at_limit_ok(self):
        LLMAsJudgeValidator(guardrail_text="x" * 4000, model="m")

    def test_too_many_positive_examples_raises(self):
        with pytest.raises(ValueError, match="positive_examples allows at most 2"):
            LLMAsJudgeValidator(
                guardrail_text=_RULE, model="m", positive_examples=["a", "b", "c"]
            )

    def test_too_many_negative_examples_raises(self):
        with pytest.raises(ValueError, match="negative_examples allows at most 2"):
            LLMAsJudgeValidator(
                guardrail_text=_RULE, model="m", negative_examples=["a", "b", "c"]
            )

    def test_two_examples_each_ok(self):
        LLMAsJudgeValidator(
            guardrail_text=_RULE,
            model="m",
            positive_examples=["a", "b"],
            negative_examples=["c", "d"],
        )

    def test_positive_example_over_length_raises(self):
        with pytest.raises(ValueError, match="positive_examples entry"):
            LLMAsJudgeValidator(
                guardrail_text=_RULE, model="m", positive_examples=["x" * 1001]
            )

    def test_negative_example_over_length_raises(self):
        with pytest.raises(ValueError, match="negative_examples entry"):
            LLMAsJudgeValidator(
                guardrail_text=_RULE, model="m", negative_examples=["x" * 1001]
            )

    def test_example_at_length_limit_ok(self):
        LLMAsJudgeValidator(
            guardrail_text=_RULE, model="m", positive_examples=["x" * 1000]
        )
