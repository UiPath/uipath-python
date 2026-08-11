"""Shared retrieve-identifier resolution for name/slug resources (MCP servers and Remote A2A agents)."""


def resolve_retrieve_identifier(name: str | None, slug: str | None) -> str:
    """Resolve a retrieve identifier, preferring the display name over the legacy slug."""
    if name is not None and slug is not None:
        raise ValueError("Specify either 'name' or 'slug', not both.")
    if name is not None:
        return name
    if slug is not None:
        return slug
    raise TypeError("Either 'name' or 'slug' must be provided.")
