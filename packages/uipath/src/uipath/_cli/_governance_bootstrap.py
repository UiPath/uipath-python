"""Shared host-side governance bootstrap for ``uipath run`` / ``uipath debug``.

Framework and agent-type labels are forwarded from
:class:`UiPathRuntimeFactorySettings` — each factory advertises its
own; the CLI never classifies the runtime.
"""

from __future__ import annotations

import atexit
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass

from uipath.core.governance import EnforcementMode, PolicyContext
from uipath.core.governance.config import is_governance_enabled
from uipath.platform import UiPath
from uipath.platform.common import UiPathConfig
from uipath.platform.governance import UiPathPlatformGovernanceProvider
from uipath.platform.governance._live_track_event_dispatcher import (
    LiveTrackEventDispatcher,
)
from uipath.runtime import UiPathRuntimeProtocol
from uipath.runtime.governance._audit.base import AuditManager
from uipath.runtime.governance._audit.metadata import GovernanceRuntimeMetadata
from uipath.runtime.governance.native import GovernanceEvaluator
from uipath.runtime.governance.native.guardrail_compensation import (
    GuardrailCompensator,
)
from uipath.runtime.governance.native.models import PolicyIndex
from uipath.runtime.governance.runtime import UiPathGovernedRuntime

from ._governance import build_policy_index_from_yaml
from ._utils._console import ConsoleLogger

console = ConsoleLogger()
logger = logging.getLogger(__name__)

__all__ = [
    "GovernanceBootstrap",
    "read_is_conversational",
    "resolve_governance",
]


@dataclass(frozen=True, slots=True)
class GovernanceBootstrap:
    """Governance wiring for one CLI run.

    ``dispose`` is idempotent, never raises, and drains the track-event
    dispatcher; call it from a ``finally``. An :mod:`atexit` fallback
    covers the case where the caller misses it.
    """

    evaluator: GovernanceEvaluator
    policy_index: PolicyIndex
    enforcement_mode: EnforcementMode
    dispose: Callable[[], None]

    def wrap_runtime(
        self,
        delegate: UiPathRuntimeProtocol,
        *,
        agent_name: str,
        runtime_id: str,
    ) -> UiPathGovernedRuntime:
        """Wrap a delegate runtime with governance evaluation."""
        return UiPathGovernedRuntime(
            delegate,
            policy_index=self.policy_index,
            enforcement_mode=self.enforcement_mode,
            evaluator=self.evaluator,
            agent_name=agent_name,
            runtime_id=runtime_id,
        )


def read_is_conversational() -> bool | None:
    """Read ``runtimeOptions.isConversational`` from the agent's uipath.json.

    Returns ``None`` when the file or field is missing — callers pass
    that through to :class:`PolicyContext` unchanged.
    """
    try:
        with open(UiPathConfig.config_file_path) as f:
            data = json.load(f)
        runtime_options = data.get("runtimeOptions") or {}
        value = runtime_options.get("isConversational")
        return value if isinstance(value, bool) else None
    except FileNotFoundError:
        return None
    except Exception as exc:
        logger.debug("Failed to read isConversational from uipath.json: %s", exc)
        return None


async def resolve_governance(
    *,
    agent_framework: str | None,
    agent_type: str | None,
) -> GovernanceBootstrap | None:
    """Fetch policy + build the governance stack, or ``None`` when disabled.

    ``agent_framework`` and ``agent_type`` are forwarded from
    :class:`UiPathRuntimeFactorySettings` and stamped on every audit
    event; ``None`` becomes ``"unknown"``.
    """
    if not is_governance_enabled():
        return None

    context = PolicyContext(is_conversational=read_is_conversational())

    try:
        sdk = UiPath()
        provider = UiPathPlatformGovernanceProvider(service=sdk.governance)
        response = await provider.get_policy_async(context)
    except Exception as exc:
        console.warning(
            f"Governance policy fetch failed - continuing without governance: {exc}"
        )
        return None

    if response.mode is None or response.mode == EnforcementMode.DISABLED:
        return None
    if not response.policies:
        return None

    try:
        policy_index = build_policy_index_from_yaml(response.policies)
    except Exception as exc:
        console.warning(
            f"Governance policy compilation failed - continuing without governance: {exc}"
        )
        return None

    # The dispatcher below owns a background thread + atexit hook, so
    # every failure path from here on must run ``dispose``.
    track_event_dispatcher: LiveTrackEventDispatcher | None = None

    def dispose() -> None:
        # Called from CLI ``finally`` — must never raise.
        dispatcher = track_event_dispatcher
        if dispatcher is None:
            return
        try:
            atexit.unregister(dispatcher.shutdown)
        except Exception:
            logger.debug("atexit.unregister failed", exc_info=True)
        try:
            dispatcher.shutdown()
        except Exception:
            logger.debug("dispatcher shutdown failed", exc_info=True)

    try:
        track_event_dispatcher = LiveTrackEventDispatcher(provider)
        atexit.register(track_event_dispatcher.shutdown)

        compensator = GuardrailCompensator(provider)
        audit_manager = AuditManager(
            track_event=track_event_dispatcher.dispatch,
            runtime_metadata=GovernanceRuntimeMetadata(
                agent_type=agent_type or "unknown",
                agent_framework=agent_framework or "unknown",
            ),
        )
        evaluator = GovernanceEvaluator(
            policy_index,
            enforcement_mode=response.mode,
            audit_manager=audit_manager,
            compensator=compensator,
        )
        console.info(
            f"Governance enabled (mode={response.mode.value}, "
            f"packs={list(policy_index.pack_names)})"
        )
    except Exception as exc:
        dispose()
        console.warning(
            f"Governance setup failed - continuing without governance: {exc}"
        )
        return None

    return GovernanceBootstrap(
        evaluator=evaluator,
        policy_index=policy_index,
        enforcement_mode=response.mode,
        dispose=dispose,
    )
