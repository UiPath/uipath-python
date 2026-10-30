"""Tests for skill bundle telemetry: the span names, types and attributes LLMOps reads."""

import json
import logging
from collections.abc import Mapping

import pytest
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from uipath.platform.skills import (
    BundleFailure,
    Skill,
    SkillBundle,
    SkillBundleRef,
    SkillSet,
    VersionMode,
)
from uipath.platform.skills._telemetry import (
    bundles_resolved_span,
    record_bundle_failed,
    record_bundles_resolved,
    record_skill_loaded,
)

FINANCE = SkillBundle(
    ref=SkillBundleRef(name="finance", folder_path="Shared/Skills"),
    version="3",
    skills=[
        Skill(name="invoice-triage", description="d", files=["SKILL.md"]),
        Skill(name="vendor-lookup", description="d", files=["SKILL.md"]),
    ],
)
OPS = SkillBundle(
    ref=SkillBundleRef(name="ops", source_name="ops-prod"),
    version="1",
    skills=[Skill(name="vendor-lookup", description="d")],
)
GHOST = BundleFailure(
    ref=SkillBundleRef(
        name="ghost", folder_path="F", version_mode=VersionMode.PINNED, version="7"
    ),
    reason="not_found",
    detail="no such bundle",
)


def _only_span(exporter: InMemorySpanExporter) -> ReadableSpan:
    [span] = exporter.get_finished_spans()
    return span


def _assert_llmops_span(span: ReadableSpan, span_type: str) -> dict[str, object]:
    """The markers the LLMOps exporters keep a span for; OTel takes primitives only."""
    attributes: dict[str, object] = dict(span.attributes or {})
    assert attributes["uipath.custom_instrumentation"] is True
    assert attributes["type"] == attributes["span_type"] == span_type
    for event in span.events:
        _assert_primitives(event.attributes or {})
    _assert_primitives(attributes)
    return attributes


def _assert_primitives(attributes: Mapping[str, object]) -> None:
    for key, value in attributes.items():
        assert isinstance(value, (str, int, bool, float)), key


def test_the_resolution_span_describes_every_bundle_and_failure(
    exporter: InMemorySpanExporter, caplog: pytest.LogCaptureFixture
) -> None:
    result = SkillSet(source="local", bundles=[FINANCE, OPS], failures=[GHOST])
    with caplog.at_level(logging.INFO):
        with bundles_resolved_span() as span:
            record_bundle_failed(span, GHOST)
            record_bundles_resolved(span, result)

    finished = _only_span(exporter)
    assert finished.name == "Skill bundles resolved"
    attributes = _assert_llmops_span(finished, "skillBundlesResolved")
    assert (
        attributes["skill.source"],
        attributes["skill.bundle.count"],
        attributes["skill.count"],
    ) == ("local", 2, 3)
    assert json.loads(str(attributes["skill.failures"])) == [
        {
            "bundle": "ghost",
            "lookup_name": "ghost",
            "folder": "F",
            "version": "7",
            "reason": "not_found",
        }
    ]
    failed, finance, ops = (dict(e.attributes or {}) for e in finished.events)
    assert [e.name for e in finished.events] == [
        "skill.bundle.failed",
        "skill.bundle.resolved",
        "skill.bundle.resolved",
    ]
    assert failed == {
        "skill.bundle.name": "ghost",
        "skill.bundle.lookup_name": "ghost",
        "skill.folder": "F",
        "skill.version": "7",
        "skill.version_mode": "pinned",
        "skill.reason": "not_found",
        "skill.detail": "no such bundle",
    }
    assert finance == {
        "skill.bundle.name": "finance",
        "skill.bundle.lookup_name": "finance",
        "skill.folder": "Shared/Skills",
        "skill.version": "3",
        "skill.version_mode": "latest",
        "skill.bundle.skill_count": 2,
    }
    assert (ops["skill.bundle.lookup_name"], ops["skill.folder"]) == ("ops-prod", "")
    assert "Skill bundle 'ghost' skipped (not_found): no such bundle" in caplog.text
    assert "finance@3 (2 skills), ops@1 (1 skills)" in caplog.text


def test_the_resolution_span_with_nothing_resolved(
    exporter: InMemorySpanExporter, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO):
        with bundles_resolved_span() as span:
            record_bundles_resolved(span, SkillSet(source="local", bundles=[]))
    attributes = dict(_only_span(exporter).attributes or {})
    assert (attributes["skill.bundle.count"], attributes["skill.count"]) == (0, 0)
    assert "Resolved 0 skill bundle(s) from local: none" in caplog.text


def test_the_skill_load_span(exporter: InMemorySpanExporter) -> None:
    record_skill_loaded(OPS, OPS.skills[0], size=7, invoked_by="user")

    span = _only_span(exporter)
    assert span.name == "Skill load - ops/vendor-lookup"
    attributes = _assert_llmops_span(span, "skillLoad")
    assert attributes == {
        "type": "skillLoad",
        "span_type": "skillLoad",
        "uipath.custom_instrumentation": True,
        "skill.bundle.name": "ops",
        "skill.bundle.lookup_name": "ops-prod",
        "skill.folder": "",
        "skill.version": "1",
        "skill.version_mode": "latest",
        "skill.name": "vendor-lookup",
        "skill.invoked_by": "user",
        "skill.bytes": 7,
    }
