"""Deprecated alias for the canonical constants module.

This module is kept as a backward-compatibility shim so existing imports keep
working. New code should import from ``uipath.platform.constants``.
"""

import warnings as _warnings

from uipath.platform.constants import *  # noqa: F401,F403

_warnings.warn(
    "uipath._utils.constants is deprecated and will be removed in a future release; "
    "import from uipath.platform.constants instead.",
    FutureWarning,
    stacklevel=2,
)
