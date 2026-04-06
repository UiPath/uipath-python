"""Guardrail decorator framework for UiPath Platform.

Provides the ``@guardrail`` decorator, built-in validators, actions, and an
adapter registry that framework integrations (e.g. *uipath-langchain*) use to
teach the decorator how to wrap their specific object types.
"""

from ._actions import BlockAction, LogAction, LoggingSeverityLevel
from ._core import GuardrailExclude
from ._enums import GuardrailExecutionStage, PIIDetectionEntityType
from ._exceptions import GuardrailBlockException
from ._guardrail import guardrail
from ._models import GuardrailAction, PIIDetectionEntity
from ._registry import GuardrailTargetAdapter, register_guardrail_adapter
from .validators import (
    BuiltInGuardrailValidator,
    CustomGuardrailValidator,
    CustomValidator,
    GuardrailValidatorBase,
    PIIValidator,
    PromptInjectionValidator,
    RuleFunction,
)

__all__ = [
    # Decorator
    "guardrail",
    # Validators
    "GuardrailValidatorBase",
    "BuiltInGuardrailValidator",
    "CustomGuardrailValidator",
    "PIIValidator",
    "PromptInjectionValidator",
    "CustomValidator",
    "RuleFunction",
    # Models & enums
    "PIIDetectionEntity",
    "PIIDetectionEntityType",
    "GuardrailExecutionStage",
    "GuardrailAction",
    # Actions
    "LogAction",
    "BlockAction",
    "LoggingSeverityLevel",
    # Exception
    "GuardrailBlockException",
    # Exclude marker
    "GuardrailExclude",
    # Adapter registry
    "GuardrailTargetAdapter",
    "register_guardrail_adapter",
]
