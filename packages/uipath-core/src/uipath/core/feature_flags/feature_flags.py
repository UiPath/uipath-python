"""Feature flags configuration for UiPath SDK.

A simple, local-only feature flag registry. Flags can be set
programmatically via :meth:`FeatureFlagsManager.configure_flags` or
supplied via environment variables named ``UIPATH_FEATURE_<FlagName>``
when nothing has been configured programmatically.

Programmatic values always take precedence over environment variables.

Example usage::

    from uipath.core.feature_flags import FeatureFlags

    # Programmatic configuration (e.g. from an upstream layer)
    FeatureFlags.configure_flags({"NewSerialization": True, "ModelOverride": "gpt-4"})

    # Check a boolean flag
    if FeatureFlags.is_flag_enabled("NewSerialization"):
        ...

    # Get an arbitrary value
    model = FeatureFlags.get_flag("ModelOverride", default="default-model")

    # Local override via environment variable
    # $ export UIPATH_FEATURE_NewSerialization=false
"""

import json
import os
from typing import Any


def _parse_env_value(raw: str) -> Any:
    """Convert an environment variable string to a Python value.

    Booleans are matched first (case-insensitive). For all other values
    JSON decoding is attempted so that dicts, lists and numbers survive
    the env-var round-trip.  Plain strings that are not valid JSON are
    returned as-is.
    """
    lower = raw.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return raw
    # Only promote structured types (dict/list); scalars stay as strings.
    if isinstance(parsed, (dict, list)):
        return parsed
    return raw


class FeatureFlagsManager:
    """Singleton registry for UiPath feature flags.

    Use the module-level :data:`FeatureFlags` instance rather than
    instantiating this class directly.
    """

    _instance: "FeatureFlagsManager | None" = None
    _flags: dict[str, Any]

    def __new__(cls) -> "FeatureFlagsManager":
        """Return the singleton instance, creating it on first call."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._flags = {}
        return cls._instance

    def configure_flags(self, flags: dict[str, Any]) -> None:
        """Merge feature flag values into the registry.

        Args:
            flags: Mapping of flag names to their values. Existing flags
                with the same name are overwritten.
        """
        self._flags.update(flags)

    def reset_flags(self) -> None:
        """Clear all configured flags."""
        self._flags.clear()

    def get_flag(self, name: str, *, default: Any = None) -> Any:
        """Return a flag value.

        Resolution order:

        1. Value set via :meth:`configure_flags` (highest priority)
        2. ``UIPATH_FEATURE_<name>`` environment variable (fallback when nothing configured)
        3. *default*

        Args:
            name: The feature flag name.
            default: Fallback when the flag is not set anywhere.
        """
        if name in self._flags:
            return self._flags[name]
        env_val = os.environ.get(f"UIPATH_FEATURE_{name}")
        if env_val is not None:
            return _parse_env_value(env_val)
        return default

    def is_flag_enabled(self, name: str, *, default: bool = False) -> bool:
        """Check whether a boolean flag is enabled.

        Uses the same resolution order as :meth:`get_flag`.

        Args:
            name: The feature flag name.
            default: Fallback when the flag is not set anywhere.
        """
        return bool(self.get_flag(name, default=default))


FeatureFlags = FeatureFlagsManager()
