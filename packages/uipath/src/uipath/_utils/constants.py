"""Deprecated alias for ``uipath.platform.common.constants``.

This module is kept as a backward-compatibility shim so existing imports keep
working. New code should import from ``uipath.platform.common.constants``.
"""

import warnings

from uipath.platform.common.constants import *  # noqa: F401,F403

warnings.warn(
    "uipath._utils.constants is deprecated and will be removed in a future "
    "release; import from uipath.platform.common.constants instead.",
    FutureWarning,
    stacklevel=2,
)
