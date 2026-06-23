"""UiPath governance shared contracts.

Evaluator-agnostic types every governance consumer references —
adapter packages (``uipath-langchain``, ``uipath-openai``, …), the
runtime layer (``uipath.runtime.governance``), and customer code that
catches :class:`GovernanceBlockException`. The full runtime / audit /
native-evaluator implementation lives in ``uipath.runtime.governance``;
this core surface is just the contracts.
"""

from .config import (
    GOVERNANCE_FEATURE_FLAG,
    is_governance_enabled,
)
from .exceptions import (
    GovernanceBlockException,
    GovernanceConfigError,
    GovernanceViolation,
    Severity,
)
from .models import Action, AuditRecord, EnforcementMode, LifecycleHook, RuleEvaluation
from .providers import (
    FiredRule,
    GovernanceCompensationProvider,
    GovernancePolicyProvider,
    GovernRequest,
    PolicyContext,
    PolicyResponse,
)

__all__ = [
    # Output models (cross adapter boundary)
    "Action",
    "AuditRecord",
    "EnforcementMode",
    "LifecycleHook",
    "RuleEvaluation",
    # Config
    "GOVERNANCE_FEATURE_FLAG",
    "is_governance_enabled",
    # Exceptions
    "GovernanceBlockException",
    "GovernanceConfigError",
    "GovernanceViolation",
    "Severity",
    # Provider protocols + wire models
    "FiredRule",
    "GovernanceCompensationProvider",
    "GovernancePolicyProvider",
    "GovernRequest",
    "PolicyContext",
    "PolicyResponse",
]
