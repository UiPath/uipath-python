import logging

from .._utils._studio_project import ResourceBuilderMetadataEntry, StudioClient

logger = logging.getLogger(__name__)

_FALLBACK: frozenset[str] = frozenset(
    {"app", "asset", "bucket", "process", "queue", "taskCatalog", "trigger"}
)


async def fetch_supported_virtual_kinds(studio_client: StudioClient) -> set[str]:
    """Return the set of resource kinds that support inline creation.

    Falls back to a static list on any failure — the caller shouldn't have to
    care whether the metadata endpoint was reachable.
    """
    try:
        metadata = await studio_client.get_resource_builder_metadata()
    except Exception as e:
        logger.debug("Resource Builder metadata fetch failed, using fallback: %s", e)
        return set(_FALLBACK)
    return _extract_supported_kinds(metadata)


def _extract_supported_kinds(
    metadata: list[ResourceBuilderMetadataEntry],
) -> set[str]:
    # metadata has one entry per (kind, type), so a kind may appear multiple times
    return {
        entry.kind
        for entry in metadata
        if any(version.supports_in_line_creation for version in entry.versions)
    }
