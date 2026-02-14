"""Feature flags configuration for UiPath SDK.

A simple, local-only feature flag registry. Flags can be set
programmatically via :func:`configure` or overridden per-flag with
environment variables named ``UIPATH_FEATURE_<FlagName>``.

Environment variables always take precedence over programmatic values.

Example usage::

    from uipath.platform.feature_flags import configure, is_enabled, get

    # Programmatic configuration (e.g. from an upstream layer)
    configure({"NewSerialization": True, "ModelOverride": "gpt-4"})

    # Check a boolean flag
    if is_enabled("NewSerialization"):
        ...

    # Get an arbitrary value
    model = get("ModelOverride", default="default-model")

    # Local override via environment variable
    # $ export UIPATH_FEATURE_NewSerialization=false
"""

import os
from typing import Any

_flags: dict[str, Any] = {}


def configure(flags: dict[str, Any]) -> None:
    """Merge feature flag values into the registry.

    Args:
        flags: Mapping of flag names to their values.  Existing flags
            with the same name are overwritten.
    """
    _flags.update(flags)


def reset() -> None:
    """Clear all configured flags.  Mainly useful in tests."""
    _flags.clear()


def _parse_env_value(raw: str) -> Any:
    """Convert an environment variable string to a Python value."""
    lower = raw.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    return raw


def get(name: str, *, default: Any = None) -> Any:
    """Return a flag value.

    Resolution order:

    1. ``UIPATH_FEATURE_<name>`` environment variable (highest priority)
    2. Value set via :func:`configure`
    3. *default*

    Args:
        name: The feature flag name.
        default: Fallback when the flag is not set anywhere.
    """
    env_val = os.environ.get(f"UIPATH_FEATURE_{name}")
    if env_val is not None:
        return _parse_env_value(env_val)
    return _flags.get(name, default)


def is_enabled(name: str, *, default: bool = False) -> bool:
    """Check whether a boolean flag is enabled.

    Uses the same resolution order as :func:`get`.

    Args:
        name: The feature flag name.
        default: Fallback when the flag is not set anywhere.
    """
    return bool(get(name, default=default))
