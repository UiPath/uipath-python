"""Public facade for the IXP design-time surface (``du_/api/designtimeapi``).

:class:`DocumentProjectsService` is the entry point reached via
``sdk.document_projects``. It groups the design-time resource services under
properties that mirror the CLI's command groups (``uip ixp projects``,
``uip ixp fields``, ...), so callers write ``sdk.document_projects.projects.list()``.

Only the ``projects`` resource is wired today; sibling resources (fields,
data-types, groups, documents, labellings, deployments) are added as their
services land, each as a new property here.
"""

from functools import cached_property

from ..common._config import UiPathApiConfig
from ..common._execution_context import UiPathExecutionContext
from ._projects_service import ProjectsService


class DocumentProjectsService:
    """Grouped access to the IXP design-time resource services.

    !!! warning "Preview Feature"
        This service is experimental. Behavior and parameters may change in
        future versions.
    """

    def __init__(
        self,
        config: UiPathApiConfig,
        execution_context: UiPathExecutionContext,
    ) -> None:
        self._config = config
        self._execution_context = execution_context

    @cached_property
    def projects(self) -> ProjectsService:
        """The projects resource — create, list, retrieve, update, delete."""
        return ProjectsService(
            config=self._config, execution_context=self._execution_context
        )
