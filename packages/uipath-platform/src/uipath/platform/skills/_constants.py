"""Names shared by the skills package and its call sites."""

SKILLS_DIR_NAME = "skills"
"""Folder that holds skill bundles, in a project and in an agent's virtual filesystem."""

MANIFEST_FILE_NAME = ".uipath-skills-manifest.json"

OVERWRITE_TYPE = "skillBundle"
"""Prefix of a bundle entry in ``resourceOverwrites`` (``skillBundle.<name>``)."""

BUNDLE_FILE_NAME = "bundle.json"
SKILL_FILE_NAME = "SKILL.md"
MAX_FILE_BYTES = 512 * 1024
MAX_BUNDLE_BYTES = 24 * 1024 * 1024
BUNDLE_RESOLVE_TIMEOUT_SECONDS = 20.0
"""Per-bundle wall clock for resolving skills at agent start.

After the first timeout the remaining bundles are skipped. The local source
copies on a worker thread, so it times out too, stopping before its next file.
"""

LOCAL_VERSION = "local"
"""The version of a bundle read from a folder without a ``bundle.json`` version."""

DEFAULT_SOURCE_KIND = "local"
"""The source used when nothing selects one: bundles read from a local folder."""

ENV_SKILLS_SOURCE = "UIPATH_SKILLS_SOURCE"
ENV_SKILLS_LOCAL_ROOT = "UIPATH_SKILLS_LOCAL_ROOT"
