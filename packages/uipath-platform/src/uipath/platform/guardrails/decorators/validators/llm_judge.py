"""LLM-as-judge guardrail validator."""

from uuid import uuid4

from uipath.platform.guardrails.guardrails import (
    BuiltInValidatorGuardrail,
    NumberParameterValue,
    StringParameterValue,
)

from ._base import BuiltInGuardrailValidator


class LLMJudgeValidator(BuiltInGuardrailValidator):
    """Validate data with an LLM acting as judge against free-form criteria.

    Delegates to the UiPath LLM-as-judge guardrail backend. Supported at all
    stages — provide judging criteria written from the perspective of the
    data being evaluated (input at PRE, output at POST).

    Args:
        criteria: Natural-language description of what the judge should check
            for. The judge passes when the data satisfies the criteria.
        model: LLM model identifier to use for judging. Defaults to ``"gpt-4o-mini"``.
        threshold: Score threshold in [0.0, 1.0] above which the judge
            considers the data compliant. Defaults to ``0.5``.

    Raises:
        ValueError: If *criteria* is empty or *threshold* is outside [0.0, 1.0].
    """

    def __init__(
        self,
        criteria: str,
        model: str = "gpt-4o-mini",
        threshold: float = 0.5,
    ) -> None:
        """Initialize LLMJudgeValidator with criteria, model, and threshold."""
        if not criteria or not criteria.strip():
            raise ValueError("criteria must be a non-empty string")
        if not 0.0 <= threshold <= 1.0:
            raise ValueError(f"threshold must be between 0.0 and 1.0, got {threshold}")
        self.criteria = criteria
        self.model = model
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
        return BuiltInValidatorGuardrail(
            id=str(uuid4()),
            name=name,
            description=description or f"LLM-as-judge ({self.model}): {self.criteria}",
            enabled_for_evals=enabled_for_evals,
            guardrail_type="builtInValidator",
            validator_type="llm_judge",
            validator_parameters=[
                StringParameterValue(
                    parameter_type="string",
                    id="criteria",
                    value=self.criteria,
                ),
                StringParameterValue(
                    parameter_type="string",
                    id="model",
                    value=self.model,
                ),
                NumberParameterValue(
                    parameter_type="number",
                    id="threshold",
                    value=self.threshold,
                ),
            ],
        )
