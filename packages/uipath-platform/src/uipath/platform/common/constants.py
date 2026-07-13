"""Deprecated alias for ``uipath.platform.constants``.

This module is kept as a backward-compatibility shim so existing imports keep
working. New code should import from ``uipath.platform.constants``.
"""

import warnings as _warnings

from uipath.platform.constants import *  # noqa: F401,F403

_warnings.warn(
    "uipath.platform.common.constants is deprecated and will be removed in a "
    "future release; import from uipath.platform.constants instead.",
    FutureWarning,
    stacklevel=2,
)
