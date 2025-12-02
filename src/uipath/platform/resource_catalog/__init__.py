"""UiPath Resource Catalog Models.

This module contains models related to UiPath Resource Catalog service.
"""

from ._resource_catalog_service import ResourceCatalogService
from .resource_catalog import Folder, Resource, ResourceType, Tag

__all__ = [
    "ResourceCatalogService",
    "Folder",
    "Resource",
    "ResourceType",
    "Tag",
]
