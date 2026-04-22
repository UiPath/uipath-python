"""Built-in GuardrailAction implementations."""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from uipath.core.guardrails import (
    GuardrailValidationResult,
    GuardrailValidationResultType,
)

from ._exceptions import GuardrailBlockException
from ._models import GuardrailAction


class LoggingSeverityLevel(int, Enum):
    """Logging severity level for :class:`LogAction`."""

    ERROR = logging.ERROR
    INFO = logging.INFO
    WARNING = logging.WARNING
    DEBUG = logging.DEBUG


@dataclass
class LogAction(GuardrailAction):
    """Log guardrail violations without stopping execution.

    Args:
        severity_level: Python logging level. Defaults to ``WARNING``.
        message: Custom log message. If omitted, the validation reason is used.
    """

    severity_level: LoggingSeverityLevel = LoggingSeverityLevel.WARNING
    message: Optional[str] = None

    def handle_validation_result(
        self,
        result: GuardrailValidationResult,
        data: str | dict[str, Any],
        guardrail_name: str,
    ) -> str | dict[str, Any] | None:
        """Log the violation and return ``None`` (no data modification)."""
        if result.result == GuardrailValidationResultType.VALIDATION_FAILED:
            msg = self.message or f"Failed: {result.reason}"
            logging.getLogger(__name__).log(
                self.severity_level,
                "[GUARDRAIL] [%s] %s",
                guardrail_name,
                msg,
            )
        return None


@dataclass
class BlockAction(GuardrailAction):
    """Block execution by raising :class:`GuardrailBlockException`.

    Framework adapters catch ``GuardrailBlockException`` at the wrapper boundary
    and convert it to their own runtime error type.

    Args:
        title: Exception title. Defaults to a message derived from the guardrail name.
        detail: Exception detail. Defaults to the validation reason.
    """

    title: Optional[str] = None
    detail: Optional[str] = None

    def handle_validation_result(
        self,
        result: GuardrailValidationResult,
        data: str | dict[str, Any],
        guardrail_name: str,
    ) -> str | dict[str, Any] | None:
        """Raise :class:`GuardrailBlockException` when validation fails."""
        if result.result == GuardrailValidationResultType.VALIDATION_FAILED:
            title = self.title or f"Guardrail [{guardrail_name}] blocked execution"
            detail = self.detail or result.reason or "Guardrail validation failed"
            raise GuardrailBlockException(title=title, detail=detail)
        return None
