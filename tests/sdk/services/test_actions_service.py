import pytest
from pytest_httpx import HTTPXMock

from uipath._config import Config
from uipath._execution_context import ExecutionContext
from uipath._services.actions_service import ActionsService
from uipath._utils.constants import HEADER_USER_AGENT
from uipath.models import Action


@pytest.fixture
def service(
    config: Config, execution_context: ExecutionContext, monkeypatch: pytest.MonkeyPatch
) -> ActionsService:
    monkeypatch.setenv("UIPATH_FOLDER_PATH", "test-folder-path")

    return ActionsService(config=config, execution_context=execution_context)


class TestActionsService:
    def test_retrieve(
        self,
        httpx_mock: HTTPXMock,
        service: ActionsService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/tasks/GenericTasks/GetTaskDataByKey?taskKey=test-id",
            status_code=200,
            json={"id": 1, "title": "Test Action"},
        )

        action = service.retrieve(
            action_key="test-id",
            app_folder_path="test-folder",
        )

        assert isinstance(action, Action)
        assert action.id == 1
        assert action.title == "Test Action"

        sent_request = httpx_mock.get_request()
        if sent_request is None:
            raise Exception("No request was sent")

        assert sent_request.method == "GET"
        assert (
            sent_request.url
            == f"{base_url}{org}{tenant}/orchestrator_/tasks/GenericTasks/GetTaskDataByKey?taskKey=test-id"
        )

        assert HEADER_USER_AGENT in sent_request.headers
        assert (
            sent_request.headers[HEADER_USER_AGENT]
            == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.ActionsService.retrieve/{version}"
        )

    @pytest.mark.anyio
    async def test_retrieve_async(
        self,
        httpx_mock: HTTPXMock,
        service: ActionsService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/tasks/GenericTasks/GetTaskDataByKey?taskKey=test-id",
            status_code=200,
            json={"id": 1, "title": "Test Action"},
        )

        action = await service.retrieve_async(
            action_key="test-id",
            app_folder_path="test-folder",
        )

        assert isinstance(action, Action)
        assert action.id == 1
        assert action.title == "Test Action"

        sent_request = httpx_mock.get_request()
        if sent_request is None:
            raise Exception("No request was sent")

        assert sent_request.method == "GET"
        assert (
            sent_request.url
            == f"{base_url}{org}{tenant}/orchestrator_/tasks/GenericTasks/GetTaskDataByKey?taskKey=test-id"
        )

        assert HEADER_USER_AGENT in sent_request.headers
        assert (
            sent_request.headers[HEADER_USER_AGENT]
            == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.ActionsService.retrieve_async/{version}"
        )

    def test_create_with_app_key(
        self,
        httpx_mock: HTTPXMock,
        service: ActionsService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/tasks/AppTasks/CreateAppTask",
            status_code=200,
            json={"id": 1, "title": "Test Action"},
        )

        action = service.create(
            title="Test Action",
            app_key="test-app-key",
            data={"test": "data"},
        )

        assert isinstance(action, Action)
        assert action.id == 1
        assert action.title == "Test Action"

    def test_create_with_assignee(
        self,
        httpx_mock: HTTPXMock,
        service: ActionsService,
        base_url: str,
        org: str,
        tenant: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("UIPATH_TENANT_ID", "test-tenant-id")

        httpx_mock.add_response(
            url=f"{base_url}{org}/apps_/default/api/v1/default/deployed-action-apps-schemas?search=test-app",
            status_code=200,
            json={
                "deployed": [
                    {
                        "systemName": "test-app",
                        "actionSchema": {
                            "key": "test-key",
                            "inputs": [],
                            "outputs": [],
                            "inOuts": [],
                            "outcomes": [],
                        },
                        "deploymentFolder": {"fullyQualifiedName": "test-folder-path"},
                    }
                ]
            },
        )

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/tasks/AppTasks/CreateAppTask",
            status_code=200,
            json={"id": 1, "title": "Test Action"},
        )

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Tasks/UiPath.Server.Configuration.OData.AssignTasks",
            status_code=200,
            json={},
        )

        action = service.create(
            title="Test Action",
            app_name="test-app",
            data={"test": "data"},
            assignee="test@example.com",
        )

        assert isinstance(action, Action)
        assert action.id == 1
        assert action.title == "Test Action"
