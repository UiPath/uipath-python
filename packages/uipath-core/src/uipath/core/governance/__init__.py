"""UiPath governance shared contracts.

Evaluator-agnostic types every governance consumer references — the
runtime layer, adapter packages, and customer code that catches
:class:`GovernanceBlockException`. The full runtime / audit /
native-evaluator implementation lives outside this package; this
core surface is just the contracts.
"""

from .config import (
    GOVERNANCE_FEATURE_FLAG,
    REGO_FEATURE_FLAG,
    is_governance_enabled,
    is_rego_enabled,
)
from .exceptions import (
    GovernanceBlockException,
    GovernanceConfigError,
    GovernanceViolation,
    Severity,
)
from .models import Action, AuditRecord, EnforcementMode, LifecycleHook, RuleEvaluation
from .providers import (
    AllPoliciesResponse,
    FiredRule,
    GovernanceCompensationProvider,
    GovernancePolicyProvider,
    GovernRequest,
    HookBundle,
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
    "REGO_FEATURE_FLAG",
    "is_governance_enabled",
    "is_rego_enabled",
    # Exceptions
    "GovernanceBlockException",
    "GovernanceConfigError",
    "GovernanceViolation",
    "Severity",
    # Provider protocols + wire models
    "AllPoliciesResponse",
    "FiredRule",
    "GovernanceCompensationProvider",
    "GovernancePolicyProvider",
    "GovernRequest",
    "HookBundle",
    "PolicyContext",
    "PolicyResponse",
]
