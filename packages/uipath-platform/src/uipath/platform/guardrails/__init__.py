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
    LogAction,
    LoggingSeverityLevel,
    PIIDetectionEntity,
    PIIDetectionEntityType,
    PIIValidator,
    PromptInjectionValidator,
    RuleFunction,
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
    "PIIValidator",
    "PromptInjectionValidator",
    "CustomValidator",
    "RuleFunction",
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
