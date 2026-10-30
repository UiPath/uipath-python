"""Deploy-time overrides for skill bundles, read from the SDK's resource-overwrite context."""

from __future__ import annotations

import logging
from typing import Mapping

from pydantic import ValidationError

from ..common._bindings import (
    ResourceOverwrite,
    SkillBundleResourceOverwrite,
    _resource_overwrites,
)
from ._constants import OVERWRITE_TYPE
from .skills import SkillBundleRef, VersionMode

logger = logging.getLogger(__name__)


def current_overwrites() -> Mapping[str, ResourceOverwrite] | None:
    """The resource overwrites active for this run, if a context installed them.

    Returns:
        The map ``ResourceOverwritesContext`` set, keyed
        ``<type>.<name>[.<folder>]``, or ``None`` outside such a context.
    """
    return _resource_overwrites.get()


def apply_skill_bundle_overwrite(
    ref: SkillBundleRef, overwrites: Mapping[str, ResourceOverwrite] | None
) -> SkillBundleRef:
    """The reference with its ``skillBundle.<name>[.<folder>]`` override applied.

    ``skillBundle.<name>.<folder>`` wins over ``skillBundle.<name>``. The
    override replaces the folder and version of the declared reference; its
    ``name`` only changes the lookup target (``source_name``), so ``ref.name``
    stays the agent-side identity. An override that yields an invalid
    reference is ignored with a warning.

    Args:
        ref: The bound bundle as the agent declares it.
        overwrites: The active overwrite map, usually ``current_overwrites()``.

    Returns:
        A new reference built from the override, or ``ref`` itself when
        nothing matches, the map is empty, or the reference is invalid.
    """
    if not overwrites:
        return ref
    candidates = (
        [f"{OVERWRITE_TYPE}.{ref.name}.{ref.folder_path}"] if ref.folder_path else []
    )
    candidates.append(f"{OVERWRITE_TYPE}.{ref.name}")
    for key in candidates:
        overwrite = overwrites.get(key)
        if not isinstance(overwrite, SkillBundleResourceOverwrite):
            continue
        try:
            return SkillBundleRef(
                name=ref.name,
                source_name=None if overwrite.name == ref.name else overwrite.name,
                folder_path=overwrite.folder_path,
                version_mode=VersionMode(overwrite.version_mode),
                version=overwrite.version,
            )
        except ValidationError as e:
            message = _first_error(e)
            bare_key = f"{OVERWRITE_TYPE}.{ref.name}"
            if key != bare_key and bare_key in overwrites:
                message += f"; the less specific key '{bare_key}' was not tried"
            logger.warning(
                "Ignoring invalid skillBundle overwrite '%s' for '%s': %s",
                key,
                ref.name,
                message,
            )
            return ref
    return ref


def _first_error(error: ValidationError) -> str:
    """The first validation message on one line, instead of pydantic's report."""
    return str(error.errors()[0]["msg"])
