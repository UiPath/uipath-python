"""Models for guardrail decorators."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from uipath.core.guardrails import GuardrailValidationResult


@dataclass
class PIIDetectionEntity:
    """PII entity configuration with detection threshold.

    Args:
        name: The entity type name (e.g. ``PIIDetectionEntityType.EMAIL``).
        threshold: Confidence threshold (0.0 to 1.0) for detection.
    """

    name: str
    threshold: float = 0.5

    def __post_init__(self) -> None:
        if not 0.0 <= self.threshold <= 1.0:
            raise ValueError(
                f"Threshold must be between 0.0 and 1.0, got {self.threshold}"
            )


@dataclass
class HarmfulContentEntity:
    """Harmful content entity configuration with severity threshold.

    Args:
        name: The entity type name (e.g. ``HarmfulContentEntityType.VIOLENCE``).
        threshold: Severity threshold (0 to 6) for detection. Defaults to ``2``.
    """

    name: str
    threshold: int = 2

    def __post_init__(self) -> None:
        if not 0 <= self.threshold <= 6:
            raise ValueError(f"Threshold must be between 0 and 6, got {self.threshold}")


class GuardrailAction(ABC):
    """Interface for defining custom actions when a guardrail violation is detected.

    Subclass this to implement custom behaviour on validation failure, such as
    logging, blocking, or content sanitisation. Built-in implementations are
    :class:`LogAction` and :class:`BlockAction`.
    """

    @abstractmethod
    def handle_validation_result(
        self,
        result: GuardrailValidationResult,
        data: str | dict[str, Any],
        guardrail_name: str,
    ) -> "str | dict[str, Any] | None":
        """Handle a guardrail validation result.

        Called when guardrail validation fails. May return modified data to
        sanitise/filter the validated content before execution continues, or
        ``None`` to leave it unchanged.

        Args:
            result: The validation result from the guardrails service.
            data: The data that was validated (string or dictionary). Depending
                on context this can be tool input, tool output, or message text.
            guardrail_name: The name of the guardrail that triggered.

        Returns:
            Modified data if the action wants to replace the original, or
            ``None`` if no modification is needed.
        """
