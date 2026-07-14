"""UiPath IXP design-time SDK (``du_/api/designtimeapi``).

This package hosts the IXP design-time services (projects, and — as they land —
fields, data-types, groups, documents, labellings, models). Reach the surface via
``sdk.document_projects``; resource services build on the shared base service
:class:`IxpDesigntimeService`.
"""

from ._base_service import (
    DESIGNTIME_API_BASE,
    DESIGNTIME_API_VERSION,
    IxpDesigntimeService,
)
from ._document_projects_service import DocumentProjectsService
from ._models import DeleteProjectResponse, Project, ProjectsPage
from ._projects_service import ProjectsService

__all__ = [
    "DocumentProjectsService",
    "ProjectsService",
    "Project",
    "ProjectsPage",
    "DeleteProjectResponse",
    "IxpDesigntimeService",
    "DESIGNTIME_API_BASE",
    "DESIGNTIME_API_VERSION",
]
