"""LLM-as-judge guardrail validator."""

from typing import Sequence
from uuid import uuid4

from uipath.platform.guardrails.guardrails import (
    BuiltInValidatorGuardrail,
    EnumParameterValue,
    NumberParameterValue,
    TextListParameterValue,
    TextParameterValue,
    ValidatorParameter,
)

from ._base import BuiltInGuardrailValidator

_MAX_GUARDRAIL_TEXT_LENGTH = 4000
_MAX_EXAMPLE_LENGTH = 1000
_DEFAULT_THRESHOLD = 2.0


class LLMJudgeValidator(BuiltInGuardrailValidator):
    """Validate data with an LLM acting as judge against a natural-language rule.

    Delegates to the UiPath LLM-as-judge built-in guardrail. Supported at all
    stages — the rule is written from the perspective of the data being
    judged (input at PRE, output at POST).

    Args:
        guardrail_text: Natural-language rule the judge enforces. Max 4000
            characters.
        model: LLM model identifier registered for the ``agent-llm-judge``
            feature in the LLM Gateway model picker.
        positive_examples: Optional payloads the judge should treat as
            compliant. Each item ≤1000 characters; the backend keeps the
            first two.
        negative_examples: Optional payloads the judge should treat as
            non-compliant. Each item ≤1000 characters; the backend keeps the
            first two.
        threshold: Strictness on a 0–6 scale; values outside that range are
            clamped by the backend. Defaults to ``2.0``.

    Raises:
        ValueError: If *guardrail_text* is empty or exceeds 4000 characters,
            *model* is empty, or any example exceeds 1000 characters.
    """

    def __init__(
        self,
        guardrail_text: str,
        model: str,
        positive_examples: Sequence[str] | None = None,
        negative_examples: Sequence[str] | None = None,
        threshold: float = _DEFAULT_THRESHOLD,
    ) -> None:
        """Initialize LLMJudgeValidator with rule text, model, and options."""
        if not guardrail_text or not guardrail_text.strip():
            raise ValueError("guardrail_text must be a non-empty string")
        if len(guardrail_text) > _MAX_GUARDRAIL_TEXT_LENGTH:
            raise ValueError(
                f"guardrail_text exceeds the {_MAX_GUARDRAIL_TEXT_LENGTH}-character limit"
            )
        if not model or not model.strip():
            raise ValueError("model must be a non-empty string")

        positives = list(positive_examples or [])
        negatives = list(negative_examples or [])
        for example in positives:
            if len(example) > _MAX_EXAMPLE_LENGTH:
                raise ValueError(
                    f"positive example exceeds the {_MAX_EXAMPLE_LENGTH}-character limit"
                )
        for example in negatives:
            if len(example) > _MAX_EXAMPLE_LENGTH:
                raise ValueError(
                    f"negative example exceeds the {_MAX_EXAMPLE_LENGTH}-character limit"
                )

        self.guardrail_text = guardrail_text
        self.model = model
        self.positive_examples = positives
        self.negative_examples = negatives
        self.threshold = threshold

    def get_built_in_guardrail(
        self,
        name: str,
        description: str | None,
        enabled_for_evals: bool,
    ) -> BuiltInValidatorGuardrail:
        """Build an LLM-as-judge :class:`BuiltInValidatorGuardrail`.

        Args:
            name: Name for the guardrail.
            description: Optional description.
            enabled_for_evals: Whether active in evaluation scenarios.

        Returns:
            Configured :class:`BuiltInValidatorGuardrail` for LLM-as-judge.
        """
        parameters: list[ValidatorParameter] = [
            TextParameterValue(
                parameter_type="text",
                id="guardrailText",
                value=self.guardrail_text,
            ),
            EnumParameterValue(
                parameter_type="enum",
                id="model",
                value=self.model,
            ),
            TextListParameterValue(
                parameter_type="text-list",
                id="positiveExamples",
                value=self.positive_examples,
            ),
            TextListParameterValue(
                parameter_type="text-list",
                id="negativeExamples",
                value=self.negative_examples,
            ),
            NumberParameterValue(
                parameter_type="number",
                id="threshold",
                value=self.threshold,
            ),
        ]

        return BuiltInValidatorGuardrail(
            id=str(uuid4()),
            name=name,
            description=description
            or f"LLM-as-judge ({self.model}): {self.guardrail_text}",
            enabled_for_evals=enabled_for_evals,
            guardrail_type="builtInValidator",
            validator_type="llm_judge",
            validator_parameters=parameters,
        )
