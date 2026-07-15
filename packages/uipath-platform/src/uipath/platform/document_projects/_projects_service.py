"""Design-time projects resource service.

:class:`ProjectsService` covers the design-time project lifecycle — list,
retrieve, create, update (title), delete — over ``du_/api/designtimeapi``.
Sub-resources of a project (fields, data-types, taxonomy, documents, models,
...) are handled by sibling services.

It builds on :class:`IxpDesigntimeService`, so writes (create/update/delete) are
**not** retried while list/retrieve keep the platform retry policy.
"""

from uipath.core.tracing import traced

from ._base_service import IxpDesigntimeService
from ._models import DeleteProjectResponse, Project, ProjectsPage

#: Default project-list page size — matches the design-time API's server-side default.
DEFAULT_LIST_LIMIT = 50

_PROJECTS = "/api/projects"
_PROJECT = "/api/projects/{name}"


class ProjectsService(IxpDesigntimeService):
    """Manage IXP design-time projects.

    Accessed as ``sdk.document_projects.projects``. Each method has an async twin
    with the ``_async`` suffix.
    """

    @traced(name="projects_list", run_type="uipath")
    def list(self, *, offset: int = 0, limit: int = DEFAULT_LIST_LIMIT) -> ProjectsPage:
        """List projects visible to the caller.

        Args:
            offset: Number of projects to skip (0–1000000).
            limit: Maximum number of projects to return (1–10000).

        Returns:
            ProjectsPage: The requested window plus the total count.
        """
        response = self._get(
            self._endpoint(_PROJECTS), params={"offset": offset, "limit": limit}
        )
        return ProjectsPage.model_validate(response.json())

    @traced(name="projects_list", run_type="uipath")
    async def list_async(
        self, *, offset: int = 0, limit: int = DEFAULT_LIST_LIMIT
    ) -> ProjectsPage:
        """Asynchronously list projects visible to the caller.

        Args:
            offset: Number of projects to skip (0–1000000).
            limit: Maximum number of projects to return (1–10000).

        Returns:
            ProjectsPage: The requested window plus the total count.
        """
        response = await self._get_async(
            self._endpoint(_PROJECTS), params={"offset": offset, "limit": limit}
        )
        return ProjectsPage.model_validate(response.json())

    @traced(name="projects_retrieve", run_type="uipath")
    def retrieve(self, project_name: str) -> Project:
        """Retrieve a project by its (slug) name.

        Args:
            project_name: The backend project name (slug), as returned by
                :meth:`create` or :meth:`list`.

        Returns:
            Project: The project.
        """
        response = self._get(self._endpoint(_PROJECT, name=project_name))
        return Project.model_validate(response.json())

    @traced(name="projects_retrieve", run_type="uipath")
    async def retrieve_async(self, project_name: str) -> Project:
        """Asynchronously retrieve a project by its (slug) name.

        Args:
            project_name: The backend project name (slug), as returned by
                :meth:`create_async` or :meth:`list_async`.

        Returns:
            Project: The project.
        """
        response = await self._get_async(self._endpoint(_PROJECT, name=project_name))
        return Project.model_validate(response.json())

    @traced(name="projects_create", run_type="uipath")
    def create(self, name: str) -> Project:
        """Create a project.

        The API slugifies ``name`` server-side; the returned :attr:`Project.name`
        is the canonical slug used to address the project in every other call.

        Args:
            name: Human-readable project name (1–116 characters).

        Returns:
            Project: The created project.
        """
        response = self._post(self._endpoint(_PROJECTS), body={"Name": name})
        return Project.model_validate(response.json())

    @traced(name="projects_create", run_type="uipath")
    async def create_async(self, name: str) -> Project:
        """Asynchronously create a project.

        The API slugifies ``name`` server-side; the returned :attr:`Project.name`
        is the canonical slug used to address the project in every other call.

        Args:
            name: Human-readable project name (1–116 characters).

        Returns:
            Project: The created project.
        """
        response = await self._post_async(
            self._endpoint(_PROJECTS), body={"Name": name}
        )
        return Project.model_validate(response.json())

    @traced(name="projects_update", run_type="uipath")
    def update(self, project_name: str, *, title: str) -> Project:
        """Update a project's display title.

        ``title`` is currently the only mutable field (keyword-only so the
        signature can grow without breaking callers).

        Args:
            project_name: The backend project name (slug).
            title: New display title (1–1024 characters).

        Returns:
            Project: The updated project.
        """
        response = self._patch(
            self._endpoint(_PROJECT, name=project_name), body={"Title": title}
        )
        return Project.model_validate(response.json())

    @traced(name="projects_update", run_type="uipath")
    async def update_async(self, project_name: str, *, title: str) -> Project:
        """Asynchronously update a project's display title.

        ``title`` is currently the only mutable field (keyword-only so the
        signature can grow without breaking callers).

        Args:
            project_name: The backend project name (slug).
            title: New display title (1–1024 characters).

        Returns:
            Project: The updated project.
        """
        response = await self._patch_async(
            self._endpoint(_PROJECT, name=project_name), body={"Title": title}
        )
        return Project.model_validate(response.json())

    @traced(name="projects_delete", run_type="uipath")
    def delete(self, project_name: str) -> DeleteProjectResponse:
        """Permanently delete a project and all its documents, taxonomy, and models.

        Irreversible.

        Args:
            project_name: The backend project name (slug).

        Returns:
            DeleteProjectResponse: A success confirmation (``status == "ok"``).
        """
        response = self._delete(self._endpoint(_PROJECT, name=project_name))
        return DeleteProjectResponse.model_validate(response.json())

    @traced(name="projects_delete", run_type="uipath")
    async def delete_async(self, project_name: str) -> DeleteProjectResponse:
        """Asynchronously and permanently delete a project and all its contents.

        Irreversible.

        Args:
            project_name: The backend project name (slug).

        Returns:
            DeleteProjectResponse: A success confirmation (``status == "ok"``).
        """
        response = await self._delete_async(self._endpoint(_PROJECT, name=project_name))
        return DeleteProjectResponse.model_validate(response.json())
