"""User prompt attacks detection guardrail validator."""

from uuid import uuid4

from uipath.platform.guardrails.guardrails import BuiltInValidatorGuardrail

from .._enums import GuardrailExecutionStage
from ._base import BuiltInGuardrailValidator


class UserPromptAttacksValidator(BuiltInGuardrailValidator):
    """Validate input for user prompt attacks via the UiPath API.

    Restricted to PRE stage only — prompt attacks are an input-only concern.
    Takes no parameters.
    """

    supported_stages = [GuardrailExecutionStage.PRE]

    def get_built_in_guardrail(
        self,
        name: str,
        description: str | None,
        enabled_for_evals: bool,
    ) -> BuiltInValidatorGuardrail:
        """Build a user prompt attacks :class:`BuiltInValidatorGuardrail`.

        Args:
            name: Name for the guardrail.
            description: Optional description.
            enabled_for_evals: Whether active in evaluation scenarios.

        Returns:
            Configured :class:`BuiltInValidatorGuardrail` for user prompt attacks.
        """
        return BuiltInValidatorGuardrail(
            id=str(uuid4()),
            name=name,
            description=description or "Detects user prompt attacks",
            enabled_for_evals=enabled_for_evals,
            guardrail_type="builtInValidator",
            validator_type="user_prompt_attacks",
            validator_parameters=[],
        )
