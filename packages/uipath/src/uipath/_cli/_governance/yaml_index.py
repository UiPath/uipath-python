"""YAML → :class:`PolicyIndex` compiler.

Lives CLI-side so the runtime layer never has to depend on ``pyyaml``
or know about the wire policy format — the runtime consumes compiled
indexes only.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import yaml

from uipath.core.governance.models import Action, LifecycleHook
from uipath.runtime.governance.native.models import (
    Check,
    Condition,
    Logic,
    PolicyIndex,
    PolicyPack,
    Rule,
    Severity,
)

logger = logging.getLogger(__name__)


_HOOK_MAP: dict[str, LifecycleHook] = {
    "before_agent": LifecycleHook.BEFORE_AGENT,
    "after_agent": LifecycleHook.AFTER_AGENT,
    "before_model": LifecycleHook.BEFORE_MODEL,
    "after_model": LifecycleHook.AFTER_MODEL,
    "wrap_tool_call": LifecycleHook.TOOL_CALL,
    "tool_call": LifecycleHook.TOOL_CALL,
    "after_tool": LifecycleHook.AFTER_TOOL,
}

_ACTION_MAP: dict[str, Action] = {
    "block": Action.DENY,
    "deny": Action.DENY,
    "log": Action.AUDIT,
    "audit": Action.AUDIT,
    "allow": Action.ALLOW,
    "require_approval": Action.ESCALATE,
    "escalate": Action.ESCALATE,
}

_SEVERITY_MAP: dict[str, Severity] = {
    "low": Severity.LOW,
    "medium": Severity.MEDIUM,
    "high": Severity.HIGH,
    "critical": Severity.CRITICAL,
}


def build_policy_index_from_yaml(yaml_text: str) -> PolicyIndex:
    """Parse YAML policy packs into a :class:`PolicyIndex`.

    Unknown check types and malformed rules are skipped with a debug log
    (partial packs preferred over failing the whole load); malformed
    YAML at the document level raises :class:`yaml.YAMLError`.
    """
    index = PolicyIndex()
    documents = list(yaml.safe_load_all(yaml_text))

    for doc in documents:
        if not isinstance(doc, dict):
            continue
        pack = _build_pack(doc)
        if pack is not None and pack.rules:
            index.add_pack(pack)

    logger.debug(
        "Built PolicyIndex from YAML: packs=%s, rules=%d",
        index.pack_names,
        index.total_rules,
    )
    return index


def _build_pack(data: dict[str, Any]) -> PolicyPack | None:
    """Build a PolicyPack from one YAML document."""
    name = data.get("standard") or data.get("name")
    if not name:
        logger.warning("Skipping pack: missing 'standard'/'name' field")
        return None

    default_action_str = data.get("default_action", "block")
    default_action = _ACTION_MAP.get(default_action_str, Action.DENY)

    rules: list[Rule] = []
    for i, rule_data in enumerate(data.get("rules", []) or []):
        if not isinstance(rule_data, dict):
            continue
        rule = _build_rule(rule_data, default_action, i)
        if rule is not None:
            rules.append(rule)

    return PolicyPack(
        name=str(name),
        version=str(data.get("version", "1.0.0")),
        description=str(data.get("description", "")),
        rules=rules,
    )


def _build_rule(
    data: dict[str, Any], default_action: Action, index: int
) -> Rule | None:
    """Build a single Rule from a YAML rule entry."""
    hook = _HOOK_MAP.get(data.get("hook", "before_model"))
    if hook is None:
        logger.warning(
            "Skipping rule %s: unknown hook %r", data.get("id"), data.get("hook")
        )
        return None

    action_str = data.get("action")
    action = (
        _ACTION_MAP.get(action_str, default_action) if action_str else default_action
    )

    default_sev = "high" if action == Action.DENY else "medium"
    severity = _SEVERITY_MAP.get(data.get("severity", default_sev), Severity.HIGH)

    checks = _build_checks(
        data.get("checks", []) or [],
        action,
        mapped_to_uipath=bool(data.get("mapped_to_uipath", False)),
        policy_enabled=bool(data.get("policy_enabled", True)),
    )

    # If checks were declared but none could be parsed (e.g. all unknown
    # types), skip the rule. A rule with zero checks "always matches" in
    # the evaluator, so keeping it would make it fire on every request.
    declared = data.get("checks", []) or []
    if declared and not checks:
        logger.warning(
            "Skipping rule %s: none of its %d declared check(s) could be parsed",
            data.get("id"),
            len(declared),
        )
        return None

    return Rule(
        rule_id=str(data.get("id", f"RULE-{index}")),
        name=str(data.get("name", data.get("id", f"RULE-{index}"))),
        clause=str(data.get("clause", data.get("owasp_ref", ""))),
        hook=hook,
        action=action,
        severity=severity,
        checks=checks,
        enabled=bool(data.get("enabled", True)),
        description=str(data.get("description", "")),
    )


def _build_checks(
    checks_data: list[dict[str, Any]],
    default_action: Action,
    *,
    mapped_to_uipath: bool = False,
    policy_enabled: bool = True,
) -> list[Check]:
    """Build the checks list for a rule.

    ``mapped_to_uipath`` / ``policy_enabled`` are rule-level flags read
    by ``guardrail_fallback`` checks so the per-check condition can
    decide whether to fire the compensating governance call.
    """
    checks: list[Check] = []
    for check_data in checks_data:
        if not isinstance(check_data, dict):
            continue
        check = _build_check(
            check_data,
            default_action,
            mapped_to_uipath=mapped_to_uipath,
            policy_enabled=policy_enabled,
        )
        if check is not None:
            checks.append(check)
    return checks


# ---------------------------------------------------------------------------
# Per-check-type condition builders
#
# Each returns ``(conditions, default_message)`` given the YAML entry for
# one check. The main :func:`_build_check` picks the right builder from
# :data:`_CHECK_BUILDERS` and layers action / logic / message resolution
# on top — keeping the dispatch flat instead of one giant if/elif chain.
# ---------------------------------------------------------------------------


def _build_regex_conditions(data: dict[str, Any]) -> tuple[list[Condition], str]:
    scope = data.get("scope", ["human", "ai"])
    field = _field_for_scope(scope)
    conditions = [
        Condition(operator="regex", field=field, value=pattern)
        for pattern in (data.get("patterns", []) or [])
    ]
    return conditions, f"Pattern matched in {scope}"


def _build_budget_conditions(data: dict[str, Any]) -> tuple[list[Condition], str]:
    return (
        _gt_conditions_from_keys(
            data,
            (
                ("max_tool_calls_per_session", "session_state.tool_calls"),
                ("max_tool_calls_per_minute", "session_state.tool_calls_per_minute"),
                (
                    "max_consecutive_tool_calls",
                    "session_state.consecutive_tool_calls",
                ),
            ),
        ),
        "Tool budget exceeded",
    )


def _build_tool_allowlist_conditions(
    data: dict[str, Any],
) -> tuple[list[Condition], str]:
    blocked_tools = data.get("blocked_tools", []) or []
    conditions = (
        [Condition(operator="in_list", field="tool_name", value=blocked_tools)]
        if blocked_tools
        else []
    )
    return conditions, "Tool not allowed"


def _build_parameter_validation_conditions(
    data: dict[str, Any],
) -> tuple[list[Condition], str]:
    conditions = [
        Condition(operator="regex", field="tool_args", value=pattern)
        for pattern in (data.get("additional_patterns", []) or [])
    ]
    return conditions, "Suspicious pattern in tool parameters"


def _build_rate_limit_conditions(
    data: dict[str, Any],
) -> tuple[list[Condition], str]:
    return (
        _gt_conditions_from_keys(
            data,
            (
                ("max_llm_calls_per_session", "session_state.llm_calls"),
                ("max_llm_calls_per_minute", "session_state.llm_calls_per_minute"),
            ),
        ),
        "Rate limit exceeded",
    )


def _build_field_regex_conditions(
    data: dict[str, Any],
) -> tuple[list[Condition], str]:
    conditions = _make_conditions(data.get("conditions", []) or [])
    return conditions, str(data.get("message", "Field regex check failed"))


def _build_data_quality_score_conditions(
    data: dict[str, Any],
) -> tuple[list[Condition], str]:
    field = data.get("field", "tool_result")
    conditions: list[Condition] = []
    if data.get("check_encoding", True):
        conditions.append(
            Condition(
                operator="encoding_concern",
                field=field,
                value={
                    "min_confidence": float(data.get("min_confidence", 0.5)),
                    "max_replacement_ratio": float(
                        data.get("max_replacement_ratio", 0.05)
                    ),
                    "min_corruption_events": int(data.get("min_corruption_events", 2)),
                },
            )
        )
    if data.get("check_entropy", True):
        conditions.append(
            Condition(
                operator="entropy_concern",
                field=field,
                value={
                    "min": float(data.get("entropy_min", 1.5)),
                    "max": float(data.get("entropy_max", 7.5)),
                },
            )
        )
    return conditions, str(data.get("message", ""))


def _build_incident_taxonomy_conditions(
    data: dict[str, Any],
) -> tuple[list[Condition], str]:
    field = data.get("field", "model_output")
    categories = data.get("categories")
    value: dict[str, Any] = {}
    if categories:
        value["categories"] = list(categories)
    conditions = [Condition(operator="incident_concern", field=field, value=value)]
    return conditions, str(data.get("message", ""))


def _build_commitment_extractor_conditions(
    data: dict[str, Any],
) -> tuple[list[Condition], str]:
    field = data.get("field", "model_output")
    conditions = [
        Condition(
            operator="commitment_concern",
            field=field,
            value={
                "require_amount": bool(data.get("require_amount", True)),
                "require_deadline": bool(data.get("require_deadline", False)),
            },
        )
    ]
    return conditions, str(data.get("message", ""))


def _build_sentiment_concern_conditions(
    data: dict[str, Any],
) -> tuple[list[Condition], str]:
    field = data.get("field", "model_input")
    threshold = float(data.get("threshold", -0.3))
    conditions = [
        Condition(
            operator="vader_concern",
            field=field,
            value={"threshold": threshold},
        )
    ]
    default_msg = f"Negative sentiment detected (VADER compound <= {threshold})"
    return conditions, default_msg


def _gt_conditions_from_keys(
    data: dict[str, Any],
    keys_to_fields: tuple[tuple[str, str], ...],
) -> list[Condition]:
    """Emit ``gt`` conditions for each YAML key present in ``data``.

    Shared by budget/rate_limit builders — they only differ in which
    (YAML key → CheckContext field) pairs they scan.
    """
    return [
        Condition(operator="gt", field=field, value=data[key])
        for key, field in keys_to_fields
        if key in data
    ]


# check_type → builder. ``guardrail_fallback`` is handled inline in
# :func:`_build_check` because it needs the rule-level flags.
_CHECK_BUILDERS: dict[str, Callable[[dict[str, Any]], tuple[list[Condition], str]]] = {
    "regex": _build_regex_conditions,
    "budget": _build_budget_conditions,
    "tool_allowlist": _build_tool_allowlist_conditions,
    "parameter_validation": _build_parameter_validation_conditions,
    "rate_limit": _build_rate_limit_conditions,
    "field_regex": _build_field_regex_conditions,
    "data_quality_score": _build_data_quality_score_conditions,
    "incident_taxonomy": _build_incident_taxonomy_conditions,
    "commitment_extractor": _build_commitment_extractor_conditions,
    "sentiment_concern": _build_sentiment_concern_conditions,
}


def _build_guardrail_fallback_conditions(
    data: dict[str, Any],
    *,
    mapped_to_uipath: bool,
    policy_enabled: bool,
) -> tuple[list[Condition], str]:
    """Compensating-control condition. Depends on rule-level flags.

    ``validator`` names which guardrail check the compensating call
    should run. The runtime's ``guardrail_fallback`` operator fires
    only when the guardrail is mapped to UiPath but disabled.
    """
    conditions = [
        Condition(
            operator="guardrail_fallback",
            field="",
            value={
                "validator": str(data.get("validator", "")),
                "mapped_to_uipath": mapped_to_uipath,
                "policy_enabled": policy_enabled,
            },
        )
    ]
    default_msg = "Guardrail disabled — compensating check needed."
    return conditions, default_msg


def _resolve_action(data: dict[str, Any], default_action: Action) -> Action:
    """Resolve the check's action against ``_ACTION_MAP`` with a default fallback."""
    action_str = data.get("action")
    if not action_str:
        return default_action
    return _ACTION_MAP.get(action_str, default_action)


def _resolve_logic(
    data: dict[str, Any],
    *,
    has_explicit_conditions: bool,
    check_type: str,
    n_conditions: int,
) -> Logic:
    """Resolve the check's ``logic`` field with the right default.

    Multi-pattern shorthand (``regex`` / ``parameter_validation``
    expanded from several patterns for one concept) defaults to ``any``
    — any pattern hitting is a match. An explicit ``conditions:`` list
    defaults to ``all`` (all must hold) and must NOT inherit the
    pattern-shorthand OR even though ``check_type`` falls back to
    ``"regex"``. Explicit ``logic`` in the YAML always wins.
    """
    if (
        not has_explicit_conditions
        and check_type in ("parameter_validation", "regex")
        and n_conditions > 1
    ):
        default_logic = "any"
    else:
        default_logic = "all"
    logic_str = str(data.get("logic", default_logic)).lower()
    try:
        return Logic(logic_str)
    except ValueError:
        return Logic.ALL


def _has_explicit_conditions(raw_conditions: Any) -> bool:
    """A ``conditions:`` list is explicit when it holds dicts with ``operator:``."""
    return (
        isinstance(raw_conditions, list)
        and bool(raw_conditions)
        and isinstance(raw_conditions[0], dict)
        and "operator" in raw_conditions[0]
    )


def _build_check(
    data: dict[str, Any],
    default_action: Action,
    *,
    mapped_to_uipath: bool = False,
    policy_enabled: bool = True,
) -> Check | None:
    """Build one Check from a YAML check entry.

    Delegates per-check-type condition-building to the small helpers
    above (dispatched via :data:`_CHECK_BUILDERS`); the ``guardrail_fallback``
    branch is inline because it needs the rule-level
    ``mapped_to_uipath`` / ``policy_enabled`` flags threaded in from
    :func:`_build_rule`. Unknown check types are skipped.
    """
    raw_conditions = data.get("conditions")
    has_explicit_conditions = _has_explicit_conditions(raw_conditions)
    check_type = data.get("type", "regex")

    if has_explicit_conditions:
        assert isinstance(raw_conditions, list)  # narrowed by _has_explicit_conditions
        conditions = list(_make_conditions(raw_conditions))
        message = str(data.get("message", ""))
    elif check_type == "guardrail_fallback":
        conditions, message = _build_guardrail_fallback_conditions(
            data,
            mapped_to_uipath=mapped_to_uipath,
            policy_enabled=policy_enabled,
        )
    else:
        builder = _CHECK_BUILDERS.get(check_type)
        if builder is None:
            logger.debug("Skipping check: unknown type %r", check_type)
            return None
        conditions, message = builder(data)

    if not conditions:
        return None

    action = _resolve_action(data, default_action)
    message = str(data.get("message", message))
    logic = _resolve_logic(
        data,
        has_explicit_conditions=has_explicit_conditions,
        check_type=check_type,
        n_conditions=len(conditions),
    )
    return Check(conditions=conditions, action=action, message=message, logic=logic)


def _make_conditions(raw: list[dict[str, Any]]) -> list[Condition]:
    """Translate a list of YAML condition dicts into Condition objects."""
    out: list[Condition] = []
    for cond in raw:
        if not isinstance(cond, dict):
            continue
        out.append(
            Condition(
                operator=str(cond.get("operator", "regex")),
                field=str(cond.get("field", "model_input")),
                value=cond.get("value", ""),
                negate=bool(cond.get("negate", False)),
            )
        )
    return out


def _field_for_scope(scope: list[str] | str) -> str:
    """Map a YAML `scope` value to the CheckContext field it targets."""
    if isinstance(scope, str):
        scope = [scope]
    if "system" in scope or "human" in scope:
        return "model_input"
    if "ai" in scope:
        return "model_output"
    if "tool_result" in scope:
        return "tool_result"
    return "model_input"
