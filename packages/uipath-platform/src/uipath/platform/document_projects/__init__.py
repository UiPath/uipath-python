"""UiPath IXP design-time SDK (``du_/api/designtimeapi``).

This package hosts the IXP design-time services (projects, taxonomy, labellings,
documents, models). It currently provides the shared base service;
resource services are added on top of :class:`IxpDesigntimeService`.
"""

from ._base_service import (
    DESIGNTIME_API_BASE,
    DESIGNTIME_API_VERSION,
    IxpDesigntimeService,
)

__all__ = [
    "IxpDesigntimeService",
    "DESIGNTIME_API_BASE",
    "DESIGNTIME_API_VERSION",
]
