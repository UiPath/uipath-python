"""Tests for the IXP design-time projects service (``document_projects/_projects_service``).

Cover the projects resource contract: the design-time URL + ``api-version``, the
PascalCase wire ⇄ snake_case model mapping (including ``created_at`` parsed to a
``datetime``), the PascalCase request bodies (``Name`` / ``Title``), project-name
percent-encoding, the paging params, and the facade wiring (``sdk.document_projects
.projects``). The no-retry-on-write contract is inherited from — and tested in —
the transport layer, so it is not re-exercised here.
"""

import json
from datetime import datetime

import pytest
from pytest_httpx import HTTPXMock

from uipath.platform import UiPathApiConfig, UiPathExecutionContext
from uipath.platform.document_projects import (
    DeleteProjectResponse,
    DocumentProjectsService,
    Project,
    ProjectsPage,
    ProjectsService,
)

_PROJECT_JSON = {
    "Id": "3d8f1b67-2c5e-4a09-bf3d-9e1a4c7b820f",
    "Name": "my-invoices",
    "Title": "My Invoices",
    "CreatedAt": "2026-04-01T10:00:00Z",
}


@pytest.fixture
def projects_service(
    config: UiPathApiConfig, execution_context: UiPathExecutionContext
) -> ProjectsService:
    return ProjectsService(config=config, execution_context=execution_context)


class TestList:
    def test_list_builds_url_with_paging_and_parses_page(
        self, httpx_mock: HTTPXMock, projects_service: ProjectsService
    ) -> None:
        httpx_mock.add_response(
            json={"Projects": [_PROJECT_JSON], "Total": 1, "Offset": 5, "Limit": 10}
        )

        page = projects_service.list(offset=5, limit=10)

        request = httpx_mock.get_request()
        assert request is not None
        assert request.method == "GET"
        assert request.url.path == "/org/tenant/du_/api/designtimeapi/api/projects"
        assert request.url.params.get("api-version") == "1.0"
        assert request.url.params.get("offset") == "5"
        assert request.url.params.get("limit") == "10"

        assert isinstance(page, ProjectsPage)
        assert page.total == 1
        assert page.offset == 5
        assert page.limit == 10
        assert len(page.projects) == 1
        assert page.projects[0].name == "my-invoices"

    def test_list_defaults_offset_zero_limit_fifty(
        self, httpx_mock: HTTPXMock, projects_service: ProjectsService
    ) -> None:
        httpx_mock.add_response(
            json={"Projects": [], "Total": 0, "Offset": 0, "Limit": 50}
        )

        projects_service.list()

        request = httpx_mock.get_request()
        assert request is not None
        assert request.url.params.get("offset") == "0"
        assert request.url.params.get("limit") == "50"


class TestRetrieve:
    def test_retrieve_encodes_name_and_maps_fields(
        self, httpx_mock: HTTPXMock, projects_service: ProjectsService
    ) -> None:
        httpx_mock.add_response(json=_PROJECT_JSON)

        # A name with a space and slash must survive as %20 / %2F.
        project = projects_service.retrieve("a b/c")

        request = httpx_mock.get_request()
        assert request is not None
        assert request.method == "GET"
        assert b"/api/projects/a%20b%2Fc" in request.url.raw_path

        assert isinstance(project, Project)
        assert project.id == "3d8f1b67-2c5e-4a09-bf3d-9e1a4c7b820f"
        assert project.name == "my-invoices"
        assert project.title == "My Invoices"
        assert isinstance(project.created_at, datetime)
        assert project.created_at.year == 2026


class TestCreate:
    def test_create_sends_name_body_and_returns_project(
        self, httpx_mock: HTTPXMock, projects_service: ProjectsService
    ) -> None:
        httpx_mock.add_response(status_code=201, json=_PROJECT_JSON)

        project = projects_service.create("My Invoices")

        request = httpx_mock.get_request()
        assert request is not None
        assert request.method == "POST"
        assert request.url.path == "/org/tenant/du_/api/designtimeapi/api/projects"
        assert json.loads(request.content) == {"Name": "My Invoices"}
        assert project.name == "my-invoices"


class TestUpdate:
    def test_update_sends_title_body_via_patch(
        self, httpx_mock: HTTPXMock, projects_service: ProjectsService
    ) -> None:
        httpx_mock.add_response(json={**_PROJECT_JSON, "Title": "Renamed"})

        project = projects_service.update("my-invoices", title="Renamed")

        request = httpx_mock.get_request()
        assert request is not None
        assert request.method == "PATCH"
        assert b"/api/projects/my-invoices" in request.url.raw_path
        assert json.loads(request.content) == {"Title": "Renamed"}
        assert project.title == "Renamed"


class TestDelete:
    def test_delete_returns_status(
        self, httpx_mock: HTTPXMock, projects_service: ProjectsService
    ) -> None:
        httpx_mock.add_response(json={"Status": "ok"})

        result = projects_service.delete("my-invoices")

        request = httpx_mock.get_request()
        assert request is not None
        assert request.method == "DELETE"
        assert b"/api/projects/my-invoices" in request.url.raw_path
        assert isinstance(result, DeleteProjectResponse)
        assert result.status == "ok"


class TestFacade:
    def test_projects_property_is_cached_projects_service(
        self, config: UiPathApiConfig, execution_context: UiPathExecutionContext
    ) -> None:
        facade = DocumentProjectsService(
            config=config, execution_context=execution_context
        )
        assert isinstance(facade.projects, ProjectsService)
        # cached_property: same instance on repeat access.
        assert facade.projects is facade.projects


class TestAsync:
    @pytest.mark.anyio
    async def test_list_async(
        self, httpx_mock: HTTPXMock, projects_service: ProjectsService
    ) -> None:
        httpx_mock.add_response(
            json={"Projects": [_PROJECT_JSON], "Total": 1, "Offset": 0, "Limit": 50}
        )

        page = await projects_service.list_async()

        request = httpx_mock.get_request()
        assert request is not None
        assert request.url.path == "/org/tenant/du_/api/designtimeapi/api/projects"
        assert page.projects[0].title == "My Invoices"

    @pytest.mark.anyio
    async def test_create_async_sends_name_body(
        self, httpx_mock: HTTPXMock, projects_service: ProjectsService
    ) -> None:
        httpx_mock.add_response(status_code=201, json=_PROJECT_JSON)

        project = await projects_service.create_async("My Invoices")

        request = httpx_mock.get_request()
        assert request is not None
        assert request.method == "POST"
        assert json.loads(request.content) == {"Name": "My Invoices"}
        assert project.name == "my-invoices"
