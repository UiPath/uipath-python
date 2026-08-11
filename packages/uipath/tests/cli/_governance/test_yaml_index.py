"""Tests for ``build_policy_index_from_yaml``."""

from __future__ import annotations

import pytest

from uipath._cli._governance.yaml_index import (
    build_policy_index_from_yaml,
)
from uipath.core.governance.models import Action, LifecycleHook
from uipath.runtime.governance.native.models import Severity


def _single_rule(yaml_text: str):
    """Compile YAML and return the single rule; fail if not exactly one."""
    idx = build_policy_index_from_yaml(yaml_text)
    rules = idx.all_rules
    assert len(rules) == 1, f"expected 1 rule, got {len(rules)}"
    return rules[0]


def test_empty_yaml_returns_empty_index() -> None:
    idx = build_policy_index_from_yaml("")
    assert idx.total_rules == 0
    assert idx.pack_names == []


def test_pack_without_rules_is_omitted() -> None:
    """Packs with no parseable rules are dropped — never registered."""
    idx = build_policy_index_from_yaml(
        """
        standard: empty-pack
        version: "1.0"
        rules: []
        """
    )
    assert idx.total_rules == 0
    assert "empty-pack" not in idx.pack_names


def test_pack_missing_name_is_skipped() -> None:
    idx = build_policy_index_from_yaml(
        """
        version: "1.0"
        rules:
          - id: r1
            hook: before_model
            checks:
              - type: regex
                patterns: ["foo"]
        """
    )
    assert idx.total_rules == 0


def test_pack_uses_standard_or_name_field() -> None:
    """Either ``standard:`` or ``name:`` works as the pack identifier."""
    a = build_policy_index_from_yaml(
        """
        standard: iso42001
        rules:
          - id: r
            hook: before_model
            checks: [{type: regex, patterns: ["x"]}]
        """
    )
    b = build_policy_index_from_yaml(
        """
        name: iso42001
        rules:
          - id: r
            hook: before_model
            checks: [{type: regex, patterns: ["x"]}]
        """
    )
    assert "iso42001" in a.pack_names
    assert "iso42001" in b.pack_names


def test_multi_document_yaml_concatenates_packs() -> None:
    # YAML doc separators must be at column 0; dedent inline.
    yaml_text = (
        "standard: pack-a\n"
        "rules:\n"
        "  - id: a-r1\n"
        "    hook: before_model\n"
        '    checks: [{type: regex, patterns: ["a"]}]\n'
        "---\n"
        "standard: pack-b\n"
        "rules:\n"
        "  - id: b-r1\n"
        "    hook: after_model\n"
        '    checks: [{type: regex, patterns: ["b"]}]\n'
    )
    idx = build_policy_index_from_yaml(yaml_text)
    assert set(idx.pack_names) == {"pack-a", "pack-b"}
    assert idx.total_rules == 2


def test_non_dict_top_level_documents_are_ignored() -> None:
    """A YAML doc that's a string / list at top level is skipped silently."""
    yaml_text = (
        "just_a_string\n"
        "---\n"
        "standard: real-pack\n"
        "rules:\n"
        "  - id: r\n"
        "    hook: before_model\n"
        '    checks: [{type: regex, patterns: ["x"]}]\n'
    )
    idx = build_policy_index_from_yaml(yaml_text)
    assert idx.pack_names == ["real-pack"]


def test_unknown_hook_skips_rule() -> None:
    """A rule referencing an unknown hook is dropped, the rest survive."""
    idx = build_policy_index_from_yaml(
        """
        standard: p
        rules:
          - id: bad
            hook: invented_hook
            checks: [{type: regex, patterns: ["x"]}]
          - id: good
            hook: before_model
            checks: [{type: regex, patterns: ["x"]}]
        """
    )
    rule_ids = [r.rule_id for r in idx.all_rules]
    assert "bad" not in rule_ids
    assert "good" in rule_ids


def test_non_dict_rule_entry_ignored() -> None:
    """Rules entries that aren't dicts (lists, scalars) are skipped."""
    idx = build_policy_index_from_yaml(
        """
        standard: p
        rules:
          - "this is a string, not a rule"
          - id: good
            hook: before_model
            checks: [{type: regex, patterns: ["x"]}]
        """
    )
    assert [r.rule_id for r in idx.all_rules] == ["good"]


def test_action_resolution_inherits_pack_default() -> None:
    """When the rule omits action, the pack's default_action is used."""
    rule = _single_rule(
        """
        standard: p
        default_action: log
        rules:
          - id: r
            hook: before_model
            checks: [{type: regex, patterns: ["x"]}]
        """
    )
    assert rule.action == Action.AUDIT  # log -> AUDIT per _ACTION_MAP


def test_action_resolution_unknown_falls_back_to_default() -> None:
    """Unknown action string falls back to the pack default."""
    rule = _single_rule(
        """
        standard: p
        default_action: deny
        rules:
          - id: r
            hook: before_model
            action: bogus
            checks: [{type: regex, patterns: ["x"]}]
        """
    )
    assert rule.action == Action.DENY


def test_severity_resolution_explicit() -> None:
    rule = _single_rule(
        """
        standard: p
        rules:
          - id: r
            hook: before_model
            severity: critical
            checks: [{type: regex, patterns: ["x"]}]
        """
    )
    assert rule.severity == Severity.CRITICAL


def test_severity_default_high_for_deny_action() -> None:
    rule = _single_rule(
        """
        standard: p
        rules:
          - id: r
            hook: before_model
            action: deny
            checks: [{type: regex, patterns: ["x"]}]
        """
    )
    assert rule.severity == Severity.HIGH


def test_severity_default_medium_for_non_deny_action() -> None:
    rule = _single_rule(
        """
        standard: p
        rules:
          - id: r
            hook: before_model
            action: log
            checks: [{type: regex, patterns: ["x"]}]
        """
    )
    assert rule.severity == Severity.MEDIUM


def test_unknown_severity_falls_back_to_high() -> None:
    rule = _single_rule(
        """
        standard: p
        rules:
          - id: r
            hook: before_model
            severity: ridiculous
            checks: [{type: regex, patterns: ["x"]}]
        """
    )
    assert rule.severity == Severity.HIGH


def test_disabled_flag_propagates() -> None:
    rule = _single_rule(
        """
        standard: p
        rules:
          - id: r
            hook: before_model
            enabled: false
            checks: [{type: regex, patterns: ["x"]}]
        """
    )
    assert rule.enabled is False


def test_rule_without_id_gets_index_based_id() -> None:
    """When ``id:`` is missing, a positional fallback ``RULE-N`` is used."""
    idx = build_policy_index_from_yaml(
        """
        standard: p
        rules:
          - hook: before_model
            checks: [{type: regex, patterns: ["x"]}]
        """
    )
    assert idx.all_rules[0].rule_id == "RULE-0"


def test_rule_with_zero_parsed_checks_is_skipped() -> None:
    """A rule whose declared checks all fail to parse is dropped.

    Without this guard, a rule with no checks ``always matches`` in the
    evaluator and would fire on every request.
    """
    idx = build_policy_index_from_yaml(
        """
        standard: p
        rules:
          - id: junk
            hook: before_model
            checks:
              - type: totally_unknown_check_type
        """
    )
    assert idx.total_rules == 0


@pytest.mark.parametrize(
    "hook_name,expected",
    [
        ("before_agent", LifecycleHook.BEFORE_AGENT),
        ("after_agent", LifecycleHook.AFTER_AGENT),
        ("before_model", LifecycleHook.BEFORE_MODEL),
        ("after_model", LifecycleHook.AFTER_MODEL),
        ("tool_call", LifecycleHook.TOOL_CALL),
        ("wrap_tool_call", LifecycleHook.TOOL_CALL),  # alias
        ("after_tool", LifecycleHook.AFTER_TOOL),
    ],
)
def test_hook_resolution(hook_name: str, expected: LifecycleHook) -> None:
    rule = _single_rule(
        f"""
        standard: p
        rules:
          - id: r
            hook: {hook_name}
            checks: [{{type: regex, patterns: ["x"]}}]
        """
    )
    assert rule.hook == expected


def test_regex_check_multi_pattern_defaults_to_any_logic() -> None:
    """Multiple regex patterns default to OR (any) — common case for ASI rules."""
    rule = _single_rule(
        """
        standard: p
        rules:
          - id: r
            hook: before_model
            checks:
              - type: regex
                patterns: ["pwn", "ignore_previous"]
        """
    )
    assert rule.checks[0].logic == "any"
    assert len(rule.checks[0].conditions) == 2


def test_regex_check_single_pattern_defaults_to_all_logic() -> None:
    rule = _single_rule(
        """
        standard: p
        rules:
          - id: r
            hook: before_model
            checks:
              - type: regex
                patterns: ["pwn"]
        """
    )
    assert rule.checks[0].logic == "all"


def test_regex_check_explicit_logic_wins() -> None:
    rule = _single_rule(
        """
        standard: p
        rules:
          - id: r
            hook: before_model
            checks:
              - type: regex
                patterns: ["a", "b"]
                logic: all
        """
    )
    assert rule.checks[0].logic == "all"


@pytest.mark.parametrize(
    "scope,expected_field",
    [
        (["human"], "model_input"),
        (["system"], "model_input"),
        (["ai"], "model_output"),
        ("ai", "model_output"),  # string form
        (["tool_result"], "tool_result"),
        (["unknown_thing"], "model_input"),  # fallback
    ],
)
def test_regex_scope_maps_to_field(scope, expected_field: str) -> None:
    rule = _single_rule(
        f"""
        standard: p
        rules:
          - id: r
            hook: before_model
            checks:
              - type: regex
                patterns: ["x"]
                scope: {scope!r}
        """
    )
    assert rule.checks[0].conditions[0].field == expected_field


def test_budget_check_max_per_session() -> None:
    rule = _single_rule(
        """
        standard: p
        rules:
          - id: r
            hook: tool_call
            checks:
              - type: budget
                max_tool_calls_per_session: 5
        """
    )
    cond = rule.checks[0].conditions[0]
    assert cond.operator == "gt"
    assert cond.field == "session_state.tool_calls"
    assert cond.value == 5


def test_budget_check_multiple_thresholds() -> None:
    """All three budget knobs become independent conditions."""
    rule = _single_rule(
        """
        standard: p
        rules:
          - id: r
            hook: tool_call
            checks:
              - type: budget
                max_tool_calls_per_session: 10
                max_tool_calls_per_minute: 5
                max_consecutive_tool_calls: 3
        """
    )
    assert len(rule.checks[0].conditions) == 3


def test_tool_allowlist_check() -> None:
    rule = _single_rule(
        """
        standard: p
        rules:
          - id: r
            hook: tool_call
            checks:
              - type: tool_allowlist
                blocked_tools: ["delete_file", "shell"]
        """
    )
    cond = rule.checks[0].conditions[0]
    assert cond.operator == "in_list"
    assert cond.field == "tool_name"
    assert cond.value == ["delete_file", "shell"]


def test_tool_allowlist_empty_blocked_list_skipped() -> None:
    """Empty ``blocked_tools`` means there's nothing to enforce — drop the rule."""
    idx = build_policy_index_from_yaml(
        """
        standard: p
        rules:
          - id: r
            hook: tool_call
            checks:
              - type: tool_allowlist
                blocked_tools: []
        """
    )
    assert idx.total_rules == 0


def test_parameter_validation_check() -> None:
    rule = _single_rule(
        """
        standard: p
        rules:
          - id: r
            hook: tool_call
            checks:
              - type: parameter_validation
                additional_patterns: ["rm -rf", "/etc/passwd"]
        """
    )
    check = rule.checks[0]
    assert len(check.conditions) == 2
    assert all(c.field == "tool_args" for c in check.conditions)
    # Multi-pattern parameter_validation defaults to OR logic
    assert check.logic == "any"


def test_rate_limit_check_session_and_minute() -> None:
    rule = _single_rule(
        """
        standard: p
        rules:
          - id: r
            hook: before_model
            checks:
              - type: rate_limit
                max_llm_calls_per_session: 20
                max_llm_calls_per_minute: 5
        """
    )
    fields = {c.field for c in rule.checks[0].conditions}
    assert fields == {
        "session_state.llm_calls",
        "session_state.llm_calls_per_minute",
    }


def test_field_regex_check_threads_through_conditions() -> None:
    rule = _single_rule(
        """
        standard: p
        rules:
          - id: r
            hook: after_model
            checks:
              - type: field_regex
                conditions:
                  - operator: regex
                    field: model_output
                    value: "(?i)password"
                message: "leaked password"
        """
    )
    check = rule.checks[0]
    assert check.message == "leaked password"
    assert check.conditions[0].operator == "regex"


def test_data_quality_score_both_encoding_and_entropy() -> None:
    rule = _single_rule(
        """
        standard: p
        rules:
          - id: r
            hook: after_tool
            checks:
              - type: data_quality_score
                field: tool_result
                min_confidence: 0.8
                entropy_min: 2.0
                entropy_max: 6.0
        """
    )
    ops = {c.operator for c in rule.checks[0].conditions}
    assert ops == {"encoding_concern", "entropy_concern"}


def test_data_quality_score_check_encoding_disabled() -> None:
    rule = _single_rule(
        """
        standard: p
        rules:
          - id: r
            hook: after_tool
            checks:
              - type: data_quality_score
                check_encoding: false
                check_entropy: true
        """
    )
    ops = [c.operator for c in rule.checks[0].conditions]
    assert "encoding_concern" not in ops
    assert "entropy_concern" in ops


def test_incident_taxonomy_with_categories() -> None:
    rule = _single_rule(
        """
        standard: p
        rules:
          - id: r
            hook: after_model
            checks:
              - type: incident_taxonomy
                field: model_output
                categories: [safety_refusal, tool_failure]
        """
    )
    cond = rule.checks[0].conditions[0]
    assert cond.operator == "incident_concern"
    assert cond.value == {"categories": ["safety_refusal", "tool_failure"]}


def test_incident_taxonomy_without_categories_uses_empty_dict() -> None:
    rule = _single_rule(
        """
        standard: p
        rules:
          - id: r
            hook: after_model
            checks:
              - type: incident_taxonomy
        """
    )
    cond = rule.checks[0].conditions[0]
    assert cond.value == {}


def test_commitment_extractor_default_flags() -> None:
    rule = _single_rule(
        """
        standard: p
        rules:
          - id: r
            hook: after_model
            checks:
              - type: commitment_extractor
        """
    )
    cond = rule.checks[0].conditions[0]
    assert cond.operator == "commitment_concern"
    assert cond.value == {"require_amount": True, "require_deadline": False}


def test_commitment_extractor_custom_flags() -> None:
    rule = _single_rule(
        """
        standard: p
        rules:
          - id: r
            hook: after_model
            checks:
              - type: commitment_extractor
                require_amount: false
                require_deadline: true
        """
    )
    cond = rule.checks[0].conditions[0]
    assert cond.value == {"require_amount": False, "require_deadline": True}


def test_sentiment_concern_check() -> None:
    rule = _single_rule(
        """
        standard: p
        rules:
          - id: r
            hook: before_model
            checks:
              - type: sentiment_concern
                threshold: -0.5
        """
    )
    cond = rule.checks[0].conditions[0]
    assert cond.operator == "vader_concern"
    assert cond.value == {"threshold": -0.5}


def test_guardrail_fallback_inherits_rule_flags() -> None:
    """Rule-level ``mapped_to_uipath`` / ``policy_enabled`` thread into the condition."""
    rule = _single_rule(
        """
        standard: p
        rules:
          - id: r
            hook: before_model
            mapped_to_uipath: true
            policy_enabled: false
            checks:
              - type: guardrail_fallback
                validator: pii_detection
        """
    )
    cond = rule.checks[0].conditions[0]
    assert cond.operator == "guardrail_fallback"
    assert cond.value == {
        "validator": "pii_detection",
        "mapped_to_uipath": True,
        "policy_enabled": False,
    }


def test_guardrail_fallback_default_flags_are_unmapped_and_enabled() -> None:
    """When the rule omits the flags, the fallback never fires (disabled-only contract)."""
    rule = _single_rule(
        """
        standard: p
        rules:
          - id: r
            hook: before_model
            checks:
              - type: guardrail_fallback
                validator: pii_detection
        """
    )
    cond = rule.checks[0].conditions[0]
    # ``guardrail_fallback`` operator fires only when mapped=True AND
    # enabled=False; defaults of False / True ensure it stays silent.
    assert cond.value["mapped_to_uipath"] is False
    assert cond.value["policy_enabled"] is True


def test_explicit_conditions_win_over_check_type() -> None:
    """Explicit ``conditions:`` short-circuits the per-type templating."""
    rule = _single_rule(
        """
        standard: p
        rules:
          - id: r
            hook: before_model
            checks:
              - type: regex   # ignored, conditions wins
                conditions:
                  - operator: contains
                    field: model_input
                    value: "secret"
                message: "no secrets"
        """
    )
    cond = rule.checks[0].conditions[0]
    assert cond.operator == "contains"  # not "regex"
    assert cond.value == "secret"
    assert rule.checks[0].message == "no secrets"


def test_explicit_conditions_negate_flag_propagates() -> None:
    rule = _single_rule(
        """
        standard: p
        rules:
          - id: r
            hook: before_model
            checks:
              - conditions:
                  - operator: contains
                    field: model_input
                    value: "allowed"
                    negate: true
        """
    )
    assert rule.checks[0].conditions[0].negate is True


def test_non_dict_condition_in_explicit_list_is_skipped() -> None:
    """A condition entry that isn't a dict is silently dropped.

    The first dict-with-``operator`` entry is what trips the
    "explicit conditions" branch in ``_build_check``; out-of-order
    scalar entries appear after the leading dict.
    """
    rule = _single_rule(
        """
        standard: p
        rules:
          - id: r
            hook: before_model
            checks:
              - conditions:
                  - operator: contains
                    field: model_input
                    value: "x"
                  - "not a dict"
        """
    )
    assert len(rule.checks[0].conditions) == 1


def test_unknown_check_type_skipped() -> None:
    """Unknown check types are dropped without taking down sibling checks."""
    idx = build_policy_index_from_yaml(
        """
        standard: p
        rules:
          - id: r
            hook: before_model
            checks:
              - type: future_check_type
              - type: regex
                patterns: ["x"]
        """
    )
    rule = idx.all_rules[0]
    # Only the regex check survived.
    assert len(rule.checks) == 1
    assert rule.checks[0].conditions[0].operator == "regex"


def test_non_dict_check_entry_skipped() -> None:
    """Checks list entries that aren't dicts are silently ignored."""
    rule = _single_rule(
        """
        standard: p
        rules:
          - id: r
            hook: before_model
            checks:
              - "scalar instead of mapping"
              - type: regex
                patterns: ["x"]
        """
    )
    assert len(rule.checks) == 1
