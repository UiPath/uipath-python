"""Governance exception types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from uipath.core.governance.models import AuditRecord

_DEFAULT_RULE_ID = "POLICY"
_DEFAULT_RULE_NAME = "Governance Policy"
_MSG_PREFIX = "[Governance Policy Violation]"


class Severity(str, Enum):
    """Severity classification for a governance violation."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class GovernanceViolation:
    """Details of a governance rule violation."""

    rule_id: str
    rule_name: str
    detail: str
    severity: Severity = Severity.HIGH


def _format_violation_message(rule_id: str, rule_name: str, detail: str) -> str:
    return f"{_MSG_PREFIX} {rule_name} ({rule_id}): {detail}"


class GovernanceBlockException(Exception):
    """Raised when a governance policy blocks an operation.

    This exception indicates that the AI agent's operation was blocked by
    a configured governance policy, not an unexpected system error.

    Prefer the classmethod constructors (:meth:`from_violation`,
    :meth:`from_audit_record`) when you have structured context — the
    default constructor is for raw-message use only.
    """

    # Error code for Orchestrator categorization
    error_code: str = "GOVERNANCE_POLICY_VIOLATION"

    def __init__(
        self,
        message: str | None = None,
        *,
        violation: GovernanceViolation | None = None,
        audit_record: AuditRecord | None = None,
        rule_id: str = _DEFAULT_RULE_ID,
        rule_name: str = _DEFAULT_RULE_NAME,
    ) -> None:
        """Construct from a pre-formatted message and optional structured context.

        Most callers should use :meth:`from_violation` or
        :meth:`from_audit_record` instead of passing structured context
        directly.
        """
        self.violation = violation
        self.audit_record = audit_record
        self.rule_id = rule_id
        self.rule_name = rule_name
        super().__init__(
            message or f"{_MSG_PREFIX} Operation blocked by governance policy."
        )

    @classmethod
    def from_violation(
        cls, violation: GovernanceViolation
    ) -> "GovernanceBlockException":
        """Build from a structured :class:`GovernanceViolation`."""
        return cls(
            message=_format_violation_message(
                violation.rule_id, violation.rule_name, violation.detail
            ),
            violation=violation,
            rule_id=violation.rule_id,
            rule_name=violation.rule_name,
        )

    @classmethod
    def from_audit_record(cls, audit_record: AuditRecord) -> "GovernanceBlockException":
        """Build from an :class:`AuditRecord` — first matched rule wins."""
        matched_rules = [e for e in audit_record.evaluations if e.matched]
        if matched_rules:
            rule = matched_rules[0]
            message = _format_violation_message(
                rule.rule_id, rule.rule_name, rule.detail or "Policy violation detected"
            )
            return cls(
                message=message,
                audit_record=audit_record,
                rule_id=rule.rule_id,
                rule_name=rule.rule_name,
            )
        return cls(
            message=(
                f"{_MSG_PREFIX} Operation blocked. "
                f"Rules evaluated: {len(audit_record.evaluations)}"
            ),
            audit_record=audit_record,
        )


class GovernanceConfigError(RuntimeError):
    """Raised when governance is misconfigured."""
