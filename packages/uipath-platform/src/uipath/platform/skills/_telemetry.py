"""Telemetry for skill bundles (contract section 9 names, DEC-31).

Both spans carry the LLMOps markers (``type``/``span_type`` and
``uipath.custom_instrumentation``) so the LLMOps exporters keep them. Until the
Agents run UI knows the ``skillBundlesResolved`` and ``skillLoad`` types it may
render them as generic custom spans.

Raw OpenTelemetry spans are used instead of ``@traced``: the resolve span
has to be yielded to the caller so bundle events can be attached to it, and
the three LLMOps marker attributes are a cross-runtime contract that the
decorator does not set.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

if TYPE_CHECKING:
    from .skills import (
        BundleFailure,
        InvokedBy,
        Skill,
        SkillBundle,
        SkillBundleRef,
        SkillSet,
    )

logger = logging.getLogger(__name__)
_tracer = trace.get_tracer("uipath.platform.skills")

# Same values as SpanType.SKILL_BUNDLES_RESOLVED / SpanType.SKILL_LOAD in the
# LLMOps span catalog (uipath-agents-python). Kept as literals: this package
# does not depend on that catalog.
SPAN_TYPE_BUNDLES_RESOLVED = "skillBundlesResolved"
SPAN_TYPE_SKILL_LOAD = "skillLoad"


@contextmanager
def bundles_resolved_span() -> Iterator[trace.Span]:
    """The one span that wraps resolving every bound bundle of a run.

    Yields:
        The current span; pass it to ``record_bundle_failed`` and
        ``record_bundles_resolved``.
    """
    with _tracer.start_as_current_span(
        "Skill bundles resolved",
        attributes=_llmops_attributes(SPAN_TYPE_BUNDLES_RESOLVED),
    ) as span:
        yield span


def record_bundles_resolved(span: trace.Span, result: SkillSet) -> None:
    """Describe on ``span`` what was resolved and what failed.

    Args:
        span: The span from ``bundles_resolved_span``.
        result: The resolved set, including the failures.
    """
    span.set_attribute("skill.source", result.source)
    span.set_attribute("skill.bundle.count", len(result.bundles))
    span.set_attribute("skill.count", sum(len(b.skills) for b in result.bundles))
    # OTel attributes only take primitives, so the failure list is JSON.
    span.set_attribute(
        "skill.failures",
        json.dumps(
            [
                {
                    "bundle": f.ref.name,
                    "lookup_name": f.ref.lookup_name,
                    "folder": f.ref.folder_path or "",
                    "version": f.ref.version or "",
                    "reason": f.reason,
                }
                for f in result.failures
            ]
        ),
    )
    for bundle in result.bundles:
        span.add_event(
            "skill.bundle.resolved",
            {
                **_ref_attributes(bundle.ref, bundle.version),
                "skill.bundle.skill_count": len(bundle.skills),
            },
        )
    logger.info(
        "Resolved %d skill bundle(s) from %s: %s",
        len(result.bundles),
        result.source,
        ", ".join(
            f"{b.ref.name}@{b.version} ({len(b.skills)} skills)" for b in result.bundles
        )
        or "none",
    )


def record_bundle_failed(span: trace.Span, failure: BundleFailure) -> None:
    """An event on ``span`` plus a warning; the run continues without the bundle.

    Args:
        span: The span from ``bundles_resolved_span``.
        failure: The bundle that was skipped and why.
    """
    span.add_event(
        "skill.bundle.failed",
        {
            **_ref_attributes(failure.ref, failure.ref.version or ""),
            "skill.reason": failure.reason,
            "skill.detail": failure.detail,
        },
    )
    logger.warning(
        "Skill bundle '%s' skipped (%s): %s",
        failure.ref.name,
        failure.reason,
        failure.detail,
    )


class SkillLoad:
    """An open ``Skill load`` span, yielded by ``skill_load_span``.

    Call ``loaded`` once the ``SKILL.md`` text is in hand, or ``fail`` when the
    read did not produce it. A span closed with neither is marked as an error.
    """

    def __init__(self, span: trace.Span, bundle: SkillBundle, skill: Skill) -> None:
        """Wrap ``span``, the current span for the load of ``skill`` from ``bundle``."""
        self.span = span
        self._bundle = bundle
        self._skill = skill
        self._settled = False

    def loaded(self, size: int) -> None:
        """Record a successful load.

        Args:
            size: UTF-8 bytes of the text handed to the reader, recorded as
                ``skill.bytes``.
        """
        self._settled = True
        self.span.set_attribute("skill.bytes", size)
        logger.info(
            "Skill loaded: %s/%s (v%s)",
            self._bundle.ref.name,
            self._skill.name,
            self._bundle.version,
        )

    def fail(self, reason: str) -> None:
        """Mark the span as an error: the read ran but returned no skill text.

        Args:
            reason: Why, recorded as the span status description.
        """
        self._settled = True
        self.span.set_status(Status(StatusCode.ERROR, reason))


@contextmanager
def skill_load_span(
    bundle: SkillBundle, skill: Skill, *, invoked_by: InvokedBy = "model"
) -> Iterator[SkillLoad]:
    """The ``Skill load`` span (DEC-31), current for the duration of the read.

    Spans started inside, such as the tool call that reads the ``SKILL.md``,
    become its children. An exception from the body is recorded on the span
    and propagates.

    Args:
        bundle: The bundle the skill belongs to.
        skill: The skill whose ``SKILL.md`` is being read.
        invoked_by: Who asked for the skill, recorded as ``skill.invoked_by``:
            ``"model"`` for a tool call, ``"user"`` when the agent's own code
            loaded it.

    Yields:
        The open load; call ``loaded`` or ``fail`` on it.
    """
    with _tracer.start_as_current_span(
        f"Skill load - {bundle.ref.name}/{skill.name}",
        attributes={
            **_llmops_attributes(SPAN_TYPE_SKILL_LOAD),
            **_ref_attributes(bundle.ref, bundle.version),
            "skill.name": skill.name,
            "skill.invoked_by": invoked_by,
        },
    ) as span:
        load = SkillLoad(span, bundle, skill)
        yield load
        if not load._settled:
            load.fail("The skill was not loaded")


def record_skill_loaded(
    bundle: SkillBundle,
    skill: Skill,
    *,
    size: int,
    invoked_by: InvokedBy = "model",
) -> None:
    """One point-in-time span for a skill that was already read (DEC-31).

    Args:
        bundle: The bundle the skill belongs to.
        skill: The skill whose ``SKILL.md`` was read.
        size: UTF-8 bytes of the text handed to the reader, recorded as
            ``skill.bytes``.
        invoked_by: Who asked for the skill, recorded as ``skill.invoked_by``:
            ``"model"`` for a tool call, ``"user"`` when the agent's own code
            loaded it.
    """
    with skill_load_span(bundle, skill, invoked_by=invoked_by) as load:
        load.loaded(size)


def _llmops_attributes(span_type: str) -> dict[str, str | bool]:
    # Mirrors BaseSpanAttributes.to_otel_attributes; LLMOps exporters drop
    # spans without uipath.custom_instrumentation.
    return {
        "type": span_type,
        "span_type": span_type,
        "uipath.custom_instrumentation": True,
    }


def _ref_attributes(ref: SkillBundleRef, version: str) -> dict[str, str]:
    """The bundle identity shared by every skill span and event."""
    return {
        "skill.bundle.name": ref.name,
        "skill.bundle.lookup_name": ref.lookup_name,
        "skill.folder": ref.folder_path or "",
        "skill.version": version,
        "skill.version_mode": ref.version_mode.value,
    }
