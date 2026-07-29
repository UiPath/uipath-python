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
    ByoValidator,
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
    LLMAsJudgeValidator,
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
    BYO_VALIDATOR_TYPE,
    BuiltInValidatorGuardrail,
    EnumListParameterValue,
    GuardrailType,
    MapEnumParameterValue,
)

__all__ = [
    # Service
    "GuardrailsService",
    # Guardrail models
    "BYO_VALIDATOR_TYPE",
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
    "ByoValidator",
    "CustomGuardrailValidator",
    "HarmfulContentValidator",
    "IntellectualPropertyValidator",
    "LLMAsJudgeValidator",
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
