"""Tests for GovernanceBlockException constructors.

The classmethod constructors (:meth:`from_violation`,
:meth:`from_audit_record`) form the documented contract that the
evaluator and adapter packages depend on — the evaluator only ever
builds a block via ``from_audit_record``. These tests pin the message
format and attribute population so a future refactor cannot silently
drop the rule id, name, or detail.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from uipath.core.governance.exceptions import (
    GovernanceBlockException,
    GovernanceViolation,
    Severity,
)
from uipath.core.governance.models import (
    Action,
    AuditRecord,
    LifecycleHook,
    RuleEvaluation,
)

# ---------------------------------------------------------------------------
# GovernanceViolation
# ---------------------------------------------------------------------------


def test_violation_defaults_to_high_severity():
    v = GovernanceViolation(rule_id="A-1", rule_name="No PII", detail="ssn leaked")
    assert v.severity == Severity.HIGH


def test_violation_severity_can_be_overridden():
    v = GovernanceViolation(
        rule_id="A-1",
        rule_name="No PII",
        detail="ssn leaked",
        severity=Severity.CRITICAL,
    )
    assert v.severity == Severity.CRITICAL


# ---------------------------------------------------------------------------
# GovernanceBlockException base constructor
# ---------------------------------------------------------------------------


def test_default_constructor_emits_prefixed_message():
    exc = GovernanceBlockException()
    assert "[Governance Policy Violation]" in str(exc)
    assert exc.violation is None
    assert exc.audit_record is None


def test_default_constructor_carries_default_rule_metadata():
    """Constructing without context still gives the documented fallback IDs."""
    exc = GovernanceBlockException()
    assert exc.rule_id == "POLICY"
    assert exc.rule_name == "Governance Policy"


def test_explicit_message_is_used_verbatim():
    exc = GovernanceBlockException("custom message")
    assert str(exc) == "custom message"


def test_error_code_constant_for_orchestrator_categorization():
    """error_code is a class-level constant the Orchestrator UI reads."""
    assert GovernanceBlockException.error_code == "GOVERNANCE_POLICY_VIOLATION"
    exc = GovernanceBlockException()
    assert exc.error_code == "GOVERNANCE_POLICY_VIOLATION"


# ---------------------------------------------------------------------------
# from_violation
# ---------------------------------------------------------------------------


def test_from_violation_populates_rule_metadata():
    v = GovernanceViolation(rule_id="A-1", rule_name="No PII", detail="ssn leaked")
    exc = GovernanceBlockException.from_violation(v)
    assert exc.rule_id == "A-1"
    assert exc.rule_name == "No PII"
    assert exc.violation is v


def test_from_violation_message_includes_rule_id_name_detail():
    v = GovernanceViolation(rule_id="A-1", rule_name="No PII", detail="ssn leaked")
    msg = str(GovernanceBlockException.from_violation(v))
    assert "A-1" in msg
    assert "No PII" in msg
    assert "ssn leaked" in msg
    assert "[Governance Policy Violation]" in msg


# ---------------------------------------------------------------------------
# from_audit_record
# ---------------------------------------------------------------------------


def _audit_record_with(*evaluations: RuleEvaluation) -> AuditRecord:
    return AuditRecord(
        timestamp=datetime.now(timezone.utc),
        agent_name="agent",
        runtime_id="run-1",
        trace_id="trace-1",
        hook=LifecycleHook.BEFORE_AGENT,
        evaluations=list(evaluations),
        final_action=Action.DENY,
    )


def test_from_audit_record_picks_first_matched_rule():
    """Even when later evaluations matched, the first matched wins the message."""
    audit = _audit_record_with(
        RuleEvaluation(
            rule_id="UNMATCHED",
            rule_name="Did not fire",
            matched=False,
            detail="",
            action=Action.ALLOW,
        ),
        RuleEvaluation(
            rule_id="MATCHED-FIRST",
            rule_name="First match",
            matched=True,
            detail="bad input",
            action=Action.DENY,
        ),
        RuleEvaluation(
            rule_id="MATCHED-SECOND",
            rule_name="Second match",
            matched=True,
            detail="also bad",
            action=Action.DENY,
        ),
    )

    exc = GovernanceBlockException.from_audit_record(audit)
    assert exc.rule_id == "MATCHED-FIRST"
    assert exc.rule_name == "First match"
    assert "bad input" in str(exc)
    assert exc.audit_record is audit


def test_from_audit_record_falls_back_when_no_match():
    """When the audit has no matches, the exception is still constructible."""
    audit = _audit_record_with(
        RuleEvaluation(
            rule_id="UNMATCHED",
            rule_name="Did not fire",
            matched=False,
            detail="",
            action=Action.ALLOW,
        )
    )

    exc = GovernanceBlockException.from_audit_record(audit)
    assert "Rules evaluated: 1" in str(exc)
    assert exc.audit_record is audit


def test_from_audit_record_matched_detail_default_when_empty():
    """A matched evaluation with empty detail still produces a sensible message."""
    audit = _audit_record_with(
        RuleEvaluation(
            rule_id="A-1",
            rule_name="No PII",
            matched=True,
            detail="",  # empty
            action=Action.DENY,
        )
    )

    msg = str(GovernanceBlockException.from_audit_record(audit))
    assert "A-1" in msg
    assert "No PII" in msg
    # Falls back to a non-empty detail string.
    assert "Policy violation detected" in msg


# ---------------------------------------------------------------------------
# Exception identity — must be a real Exception so callers can catch broadly
# ---------------------------------------------------------------------------


def test_block_exception_is_exception_subclass():
    assert issubclass(GovernanceBlockException, Exception)


def test_block_exception_can_be_caught_via_base_exception():
    try:
        raise GovernanceBlockException.from_violation(
            GovernanceViolation(rule_id="A-1", rule_name="X", detail="d")
        )
    except Exception as e:  # noqa: BLE001 - intentional broad catch
        assert isinstance(e, GovernanceBlockException)
    else:
        pytest.fail("Did not raise")
