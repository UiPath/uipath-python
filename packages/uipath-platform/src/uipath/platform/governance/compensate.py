"""Re-exports of compensation models from :mod:`uipath.core.governance`.

The wire-shape models live in ``uipath-core`` so the runtime can depend on
the protocol contract without importing ``uipath-platform``. This module
keeps the existing ``uipath.platform.governance`` import paths working.
"""

from uipath.core.governance import FiredRule, GovernRequest

__all__ = ["FiredRule", "GovernRequest"]
