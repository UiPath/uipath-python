"""Harmful content detection guardrail validator."""

from typing import Any, Sequence
from uuid import uuid4

from uipath.platform.guardrails.guardrails import (
    BuiltInValidatorGuardrail,
    EnumListParameterValue,
    MapEnumParameterValue,
)

from .._models import HarmfulContentEntity
from ._base import BuiltInGuardrailValidator


class HarmfulContentValidator(BuiltInGuardrailValidator):
    """Validate data for harmful content using the UiPath API.

    Supported at all stages (PRE, POST, PRE_AND_POST).

    Args:
        entities: One or more :class:`~uipath.platform.guardrails.decorators.HarmfulContentEntity`
            instances specifying which harmful content categories to detect
            and their severity thresholds.

    Raises:
        ValueError: If *entities* is empty.
    """

    def __init__(self, entities: Sequence[HarmfulContentEntity]) -> None:
        """Initialize HarmfulContentValidator with entities to detect."""
        if not entities:
            raise ValueError("entities must be provided and non-empty")
        self.entities = list(entities)

    def get_built_in_guardrail(
        self,
        name: str,
        description: str | None,
        enabled_for_evals: bool,
    ) -> BuiltInValidatorGuardrail:
        """Build a harmful content :class:`BuiltInValidatorGuardrail`.

        Args:
            name: Name for the guardrail.
            description: Optional description.
            enabled_for_evals: Whether active in evaluation scenarios.

        Returns:
            Configured :class:`BuiltInValidatorGuardrail` for harmful content detection.
        """
        entity_names = [entity.name for entity in self.entities]
        entity_thresholds: dict[str, Any] = {
            entity.name: entity.threshold for entity in self.entities
        }

        return BuiltInValidatorGuardrail(
            id=str(uuid4()),
            name=name,
            description=description
            or f"Detects harmful content: {', '.join(entity_names)}",
            enabled_for_evals=enabled_for_evals,
            guardrail_type="builtInValidator",
            validator_type="harmful_content",
            validator_parameters=[
                EnumListParameterValue(
                    parameter_type="enum-list",
                    id="harmfulContentEntities",
                    value=entity_names,
                ),
                MapEnumParameterValue(
                    parameter_type="map-enum",
                    id="harmfulContentEntityThresholds",
                    value=entity_thresholds,
                ),
            ],
        )
