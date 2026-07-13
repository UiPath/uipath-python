"""Governance services for the UiPath Platform.

Exposes the agenticgovernance_ ingress: tenant-controlled policy packs
served centrally so policy decisions can change without redeploying
agents.
"""

from ._governance_provider import UiPathPlatformGovernanceProvider
from ._governance_service import GovernanceService
from .compensate import FiredRule, GovernRequest
from .policy import AllPoliciesResponse, HookBundle, PolicyContext, PolicyResponse

# ``_live_track_event_dispatcher.LiveTrackEventDispatcher`` is intentionally
# **not** re-exported. It is host-wiring glue (the runtime sink's
# non-blocking ``track_event`` adapter), not a customer-facing API.
# Internal callers import it via the explicit private path:
#
#     from uipath.platform.governance._live_track_event_dispatcher import (
#         LiveTrackEventDispatcher,
#     )

__all__ = [
    "AllPoliciesResponse",
    "FiredRule",
    "GovernRequest",
    "GovernanceService",
    "HookBundle",
    "PolicyContext",
    "PolicyResponse",
    "UiPathPlatformGovernanceProvider",
]
