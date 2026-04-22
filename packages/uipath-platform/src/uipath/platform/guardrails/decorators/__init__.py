"""Guardrail decorator framework for UiPath Platform.

Provides the ``@guardrail`` decorator, built-in validators, actions, and an
adapter registry that framework integrations (e.g. *uipath-langchain*) use to
teach the decorator how to wrap their specific object types.
"""

from ._actions import BlockAction, LogAction, LoggingSeverityLevel
from ._core import GuardrailExclude
from ._enums import (
    GuardrailExecutionStage,
    HarmfulContentEntityType,
    IntellectualPropertyEntityType,
    PIIDetectionEntityType,
)
from ._exceptions import GuardrailBlockException
from ._guardrail import guardrail
from ._models import GuardrailAction, HarmfulContentEntity, PIIDetectionEntity
from ._registry import GuardrailTargetAdapter, register_guardrail_adapter
from .validators import (
    BuiltInGuardrailValidator,
    CustomGuardrailValidator,
    CustomValidator,
    GuardrailValidatorBase,
    HarmfulContentValidator,
    IntellectualPropertyValidator,
    PIIValidator,
    PromptInjectionValidator,
    RuleFunction,
    UserPromptAttacksValidator,
)

__all__ = [
    # Decorator
    "guardrail",
    # Validators
    "GuardrailValidatorBase",
    "BuiltInGuardrailValidator",
    "CustomGuardrailValidator",
    "HarmfulContentValidator",
    "IntellectualPropertyValidator",
    "PIIValidator",
    "PromptInjectionValidator",
    "UserPromptAttacksValidator",
    "CustomValidator",
    "RuleFunction",
    # Models & enums
    "HarmfulContentEntity",
    "HarmfulContentEntityType",
    "IntellectualPropertyEntityType",
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
