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
MAX_DESCRIPTION_CHARS = 1024
"""Longest skill description kept, the Agent Skills limit."""

BUNDLE_RESOLVE_TIMEOUT_SECONDS = 20.0
"""Per-bundle wall clock for resolving skills at agent start.

After the first timeout the remaining bundles are skipped. It stops the
Orchestrator source's HTTP calls. Copying files, and unpacking a downloaded
archive, runs without yielding to the event loop, so the limit does not stop
it; ``MAX_BUNDLE_BYTES`` and ``MAX_ARCHIVE_BYTES`` bound it instead.
"""

LOCAL_VERSION = "local"
"""The version of a bundle read from a folder without a ``bundle.json`` version."""

DEFAULT_SOURCE_KIND = "orchestrator"
"""The source used when nothing selects one: bundles fetched from Orchestrator."""

ENV_SKILLS_SOURCE = "UIPATH_SKILLS_SOURCE"
ENV_SKILLS_LOCAL_ROOT = "UIPATH_SKILLS_LOCAL_ROOT"

SKILL_BUNDLES_ENDPOINT = "orchestrator_/api/skill-bundles"
"""Lists the skill bundles of the folder in the request's folder header."""

BUNDLE_ENDPOINT = "orchestrator_/api/bundles/{key}"
"""One bundle's content: ``/versions/{version}`` and ``/versions/{version}/archive``."""

LOOKUP_PAGE_SIZE = 100
"""Bundles asked for per page when looking a bundle up by name."""

LOOKUP_MAX_PAGES = 10
"""Pages read before a name lookup gives up; ``search`` matches part of a name."""

MAX_ARCHIVE_BYTES = 2 * MAX_BUNDLE_BYTES
"""Largest bundle version downloaded, by the sizes in its manifest.

Above ``MAX_BUNDLE_BYTES`` because hidden and oversized files are downloaded but
not copied; the copy itself stays within ``MAX_BUNDLE_BYTES``.
"""

MAX_ARCHIVE_ENTRIES = 4096
"""Most files a bundle version may hold."""
