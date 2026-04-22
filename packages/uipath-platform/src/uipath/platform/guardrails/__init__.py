"""UiPath Guardrails Models.

This module contains models related to UiPath Guardrails service.
"""

# 2.3.0 remove
from uipath.core.guardrails import (
    BaseGuardrail,
    DeterministicGuardrail,
    DeterministicGuardrailsService,
    GuardrailScope,
    GuardrailValidationResult,
    GuardrailValidationResultType,
)

from ._guardrails_service import GuardrailsService
from .decorators import (
    BlockAction,
    BuiltInGuardrailValidator,
    CustomGuardrailValidator,
    CustomValidator,
    GuardrailAction,
    GuardrailBlockException,
    GuardrailExclude,
    GuardrailExecutionStage,
    GuardrailTargetAdapter,
    GuardrailValidatorBase,
    HarmfulContentEntity,
    HarmfulContentEntityType,
    HarmfulContentValidator,
    IntellectualPropertyEntityType,
    IntellectualPropertyValidator,
    LogAction,
    LoggingSeverityLevel,
    PIIDetectionEntity,
    PIIDetectionEntityType,
    PIIValidator,
    PromptInjectionValidator,
    RuleFunction,
    UserPromptAttacksValidator,
    guardrail,
    register_guardrail_adapter,
)
from .guardrails import (
    BuiltInValidatorGuardrail,
    EnumListParameterValue,
    GuardrailType,
    MapEnumParameterValue,
)

__all__ = [
    # Service
    "GuardrailsService",
    # Guardrail models
    "BuiltInValidatorGuardrail",
    "GuardrailType",
    "GuardrailValidationResultType",
    "BaseGuardrail",
    "GuardrailScope",
    "DeterministicGuardrail",
    "DeterministicGuardrailsService",
    "GuardrailValidationResult",
    "EnumListParameterValue",
    "MapEnumParameterValue",
    # Decorator framework
    "guardrail",
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
    "HarmfulContentEntity",
    "HarmfulContentEntityType",
    "IntellectualPropertyEntityType",
    "PIIDetectionEntity",
    "PIIDetectionEntityType",
    "GuardrailExecutionStage",
    "GuardrailAction",
    "LogAction",
    "BlockAction",
    "LoggingSeverityLevel",
    "GuardrailBlockException",
    "GuardrailExclude",
    "GuardrailTargetAdapter",
    "register_guardrail_adapter",
]
