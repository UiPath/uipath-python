"""Intellectual property detection guardrail validator."""

from typing import Sequence
from uuid import uuid4

from uipath.platform.guardrails.guardrails import (
    BuiltInValidatorGuardrail,
    EnumListParameterValue,
)

from .._enums import GuardrailExecutionStage
from ._base import BuiltInGuardrailValidator


class IntellectualPropertyValidator(BuiltInGuardrailValidator):
    """Validate output for intellectual property violations using the UiPath API.

    Restricted to POST stage only — IP detection is an output-only concern.

    Args:
        entities: One or more entity type strings (e.g.
            ``IntellectualPropertyEntityType.TEXT``).

    Raises:
        ValueError: If *entities* is empty.
    """

    supported_stages = [GuardrailExecutionStage.POST]

    def __init__(self, entities: Sequence[str]) -> None:
        """Initialize IntellectualPropertyValidator with entities to detect."""
        if not entities:
            raise ValueError("entities must be provided and non-empty")
        self.entities = list(entities)

    def get_built_in_guardrail(
        self,
        name: str,
        description: str | None,
        enabled_for_evals: bool,
    ) -> BuiltInValidatorGuardrail:
        """Build an intellectual property :class:`BuiltInValidatorGuardrail`.

        Args:
            name: Name for the guardrail.
            description: Optional description.
            enabled_for_evals: Whether active in evaluation scenarios.

        Returns:
            Configured :class:`BuiltInValidatorGuardrail` for IP detection.
        """
        return BuiltInValidatorGuardrail(
            id=str(uuid4()),
            name=name,
            description=description
            or f"Detects intellectual property: {', '.join(self.entities)}",
            enabled_for_evals=enabled_for_evals,
            guardrail_type="builtInValidator",
            validator_type="intellectual_property",
            validator_parameters=[
                EnumListParameterValue(
                    parameter_type="enum-list",
                    id="ipEntities",
                    value=self.entities,
                ),
            ],
        )
