"""PII detection guardrail validator."""

from typing import Any, Sequence
from uuid import uuid4

from uipath.platform.guardrails.guardrails import (
    BuiltInValidatorGuardrail,
    EnumListParameterValue,
    MapEnumParameterValue,
)

from .._models import PIIDetectionEntity
from ._base import BuiltInGuardrailValidator


class PIIValidator(BuiltInGuardrailValidator):
    """Validate data for PII entities using the UiPath PII detection API.

    Supported at all stages.

    Args:
        entities: One or more :class:`~uipath.platform.guardrails.decorators.PIIDetectionEntity`
            instances specifying which PII types to detect and their confidence thresholds.

    Raises:
        ValueError: If *entities* is empty.
    """

    def __init__(self, entities: Sequence[PIIDetectionEntity]) -> None:
        """Initialize PIIValidator with a list of entities to detect."""
        if not entities:
            raise ValueError("entities must be provided and non-empty")
        self.entities = list(entities)

    def get_built_in_guardrail(
        self,
        name: str,
        description: str | None,
        enabled_for_evals: bool,
    ) -> BuiltInValidatorGuardrail:
        """Build a PII detection :class:`BuiltInValidatorGuardrail`.

        Args:
            name: Name for the guardrail.
            description: Optional description.
            enabled_for_evals: Whether active in evaluation scenarios.

        Returns:
            Configured :class:`BuiltInValidatorGuardrail` for PII detection.
        """
        entity_names = [entity.name for entity in self.entities]
        entity_thresholds: dict[str, Any] = {
            entity.name: entity.threshold for entity in self.entities
        }

        return BuiltInValidatorGuardrail(
            id=str(uuid4()),
            name=name,
            description=description
            or f"Detects PII entities: {', '.join(entity_names)}",
            enabled_for_evals=enabled_for_evals,
            guardrail_type="builtInValidator",
            validator_type="pii_detection",
            validator_parameters=[
                EnumListParameterValue(
                    parameter_type="enum-list",
                    id="entities",
                    value=entity_names,
                ),
                MapEnumParameterValue(
                    parameter_type="map-enum",
                    id="entityThresholds",
                    value=entity_thresholds,
                ),
            ],
        )
