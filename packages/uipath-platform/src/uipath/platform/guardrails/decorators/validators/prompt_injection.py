"""Prompt injection detection guardrail validator."""

from uuid import uuid4

from uipath.platform.guardrails.guardrails import (
    BuiltInValidatorGuardrail,
    NumberParameterValue,
)

from .._enums import GuardrailExecutionStage
from ._base import BuiltInGuardrailValidator


class PromptInjectionValidator(BuiltInGuardrailValidator):
    """Validate input for prompt injection attacks via the UiPath API.

    Restricted to PRE stage only — prompt injection is an input-only concern.

    Args:
        threshold: Detection confidence threshold (0.0–1.0). Defaults to ``0.5``.

    Raises:
        ValueError: If *threshold* is outside [0.0, 1.0].
    """

    supported_stages = [GuardrailExecutionStage.PRE]

    def __init__(self, threshold: float = 0.5) -> None:
        """Initialize PromptInjectionValidator with a detection threshold."""
        if not 0.0 <= threshold <= 1.0:
            raise ValueError(f"threshold must be between 0.0 and 1.0, got {threshold}")
        self.threshold = threshold

    def get_built_in_guardrail(
        self,
        name: str,
        description: str | None,
        enabled_for_evals: bool,
    ) -> BuiltInValidatorGuardrail:
        """Build a prompt injection :class:`BuiltInValidatorGuardrail`.

        Args:
            name: Name for the guardrail.
            description: Optional description.
            enabled_for_evals: Whether active in evaluation scenarios.

        Returns:
            Configured :class:`BuiltInValidatorGuardrail` for prompt injection.
        """
        return BuiltInValidatorGuardrail(
            id=str(uuid4()),
            name=name,
            description=description
            or f"Detects prompt injection with threshold {self.threshold}",
            enabled_for_evals=enabled_for_evals,
            guardrail_type="builtInValidator",
            validator_type="prompt_injection",
            validator_parameters=[
                NumberParameterValue(
                    parameter_type="number",
                    id="threshold",
                    value=self.threshold,
                ),
            ],
        )
