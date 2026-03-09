from typing import Any

import pytest
from pytest_httpx import HTTPXMock

from uipath.platform import UiPathApiConfig, UiPathExecutionContext
from uipath.platform.action_center import Task
from uipath.platform.action_center._tasks_service import TasksService
from uipath.platform.common.constants import HEADER_USER_AGENT


@pytest.fixture
def service(
    config: UiPathApiConfig,
    execution_context: UiPathExecutionContext,
    monkeypatch: pytest.MonkeyPatch,
) -> TasksService:
    monkeypatch.setenv("UIPATH_FOLDER_PATH", "test-folder-path")

    return TasksService(config=config, execution_context=execution_context)


class TestTasksService:
    def test_retrieve(
        self,
        httpx_mock: HTTPXMock,
        service: TasksService,
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

        assert isinstance(action, Task)
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
            == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.TasksService.retrieve/{version}"
        )

    @pytest.mark.anyio
    async def test_retrieve_async(
        self,
        httpx_mock: HTTPXMock,
        service: TasksService,
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

        assert isinstance(action, Task)
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
            == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.TasksService.retrieve_async/{version}"
        )

    def test_create_with_app_key(
        self,
        httpx_mock: HTTPXMock,
        service: TasksService,
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

        assert isinstance(action, Task)
        assert action.id == 1
        assert action.title == "Test Action"

    def test_create_with_assignee(
        self,
        httpx_mock: HTTPXMock,
        service: TasksService,
        base_url: str,
        org: str,
        tenant: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("UIPATH_TENANT_ID", "test-tenant-id")

        httpx_mock.add_response(
            url=f"{base_url}{org}/apps_/default/api/v1/default/deployed-action-apps-schemas?search=test-app&filterByDeploymentTitle=true",
            status_code=200,
            json={
                "deployed": [
                    {
                        "systemName": "test-app",
                        "deploymentTitle": "test-app",
                        "actionSchema": {
                            "key": "test-key",
                            "inputs": [],
                            "outputs": [],
                            "inOuts": [],
                            "outcomes": [],
                        },
                        "deploymentFolder": {
                            "fullyQualifiedName": "test-folder-path",
                            "key": "test-folder-key",
                        },
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

        assert isinstance(action, Task)
        assert action.id == 1
        assert action.title == "Test Action"


def _make_deployed_app(
    name: str,
    folder_path: str,
    folder_key: str,
    system_name: str | None = None,
) -> dict[str, Any]:
    return {
        "systemName": system_name or name,
        "deploymentTitle": name,
        "actionSchema": {
            "key": f"{name}-schema-key",
            "inputs": [],
            "outputs": [],
            "inOuts": [],
            "outcomes": [],
        },
        "deploymentFolder": {
            "fullyQualifiedName": folder_path,
            "key": folder_key,
        },
    }


class TestCreateFiltersByFolder:
    """Tests for folder filtering when creating tasks via app_name lookup."""

    def _make_tasks_service(
        self,
        config: UiPathApiConfig,
        execution_context: UiPathExecutionContext,
        monkeypatch: pytest.MonkeyPatch,
        folder_key: str | None = None,
        folder_path: str | None = None,
    ) -> TasksService:
        if folder_key:
            monkeypatch.setenv("UIPATH_FOLDER_KEY", folder_key)
        if folder_path:
            monkeypatch.setenv("UIPATH_FOLDER_PATH", folder_path)
        return TasksService(config=config, execution_context=execution_context)

    def _mock_app_schemas_response(
        self,
        httpx_mock: HTTPXMock,
        base_url: str,
        org: str,
        app_name: str,
        deployed_apps: list[dict[str, Any]],
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}{org}/apps_/default/api/v1/default/deployed-action-apps-schemas?search={app_name}&filterByDeploymentTitle=true",
            status_code=200,
            json={"deployed": deployed_apps},
        )

    def _mock_create_task_response(
        self,
        httpx_mock: HTTPXMock,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/tasks/AppTasks/CreateAppTask",
            status_code=200,
            json={"id": 1, "title": "Test Action"},
        )

    def test_create_filters_by_app_folder_key(
        self,
        httpx_mock: HTTPXMock,
        config: UiPathApiConfig,
        execution_context: UiPathExecutionContext,
        monkeypatch: pytest.MonkeyPatch,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        monkeypatch.setenv("UIPATH_TENANT_ID", "test-tenant-id")
        tasks_service = self._make_tasks_service(config, execution_context, monkeypatch)
        self._mock_app_schemas_response(
            httpx_mock,
            base_url,
            org,
            "my-app",
            [
                _make_deployed_app(
                    "my-app", "folder-a", "key-a", system_name="my-app-a"
                ),
                _make_deployed_app(
                    "my-app", "folder-b", "key-b", system_name="my-app-b"
                ),
            ],
        )
        self._mock_create_task_response(httpx_mock, base_url, org, tenant)

        task = tasks_service.create(
            title="Test",
            app_name="my-app",
            app_folder_key="key-b",
            app_folder_path=None,
        )

        assert isinstance(task, Task)
        create_request = [
            r for r in httpx_mock.get_requests() if "CreateAppTask" in str(r.url)
        ][0]
        # systemName from the key-b deployment is used as appId in the request
        assert b"my-app-b" in create_request.content

    @pytest.mark.anyio
    async def test_create_async_filters_by_app_folder_key(
        self,
        httpx_mock: HTTPXMock,
        config: UiPathApiConfig,
        execution_context: UiPathExecutionContext,
        monkeypatch: pytest.MonkeyPatch,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        monkeypatch.setenv("UIPATH_TENANT_ID", "test-tenant-id")
        tasks_service = self._make_tasks_service(config, execution_context, monkeypatch)
        self._mock_app_schemas_response(
            httpx_mock,
            base_url,
            org,
            "my-app",
            [
                _make_deployed_app(
                    "my-app", "folder-a", "key-a", system_name="my-app-a"
                ),
                _make_deployed_app(
                    "my-app", "folder-b", "key-b", system_name="my-app-b"
                ),
            ],
        )
        self._mock_create_task_response(httpx_mock, base_url, org, tenant)

        task = await tasks_service.create_async(
            title="Test",
            app_name="my-app",
            app_folder_key="key-b",
            app_folder_path=None,
        )

        assert isinstance(task, Task)
        create_request = [
            r for r in httpx_mock.get_requests() if "CreateAppTask" in str(r.url)
        ][0]
        # systemName from the key-b deployment is used as appId in the request
        assert b"my-app-b" in create_request.content

    def test_create_filters_by_app_folder_path(
        self,
        httpx_mock: HTTPXMock,
        config: UiPathApiConfig,
        execution_context: UiPathExecutionContext,
        monkeypatch: pytest.MonkeyPatch,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        monkeypatch.setenv("UIPATH_TENANT_ID", "test-tenant-id")
        tasks_service = self._make_tasks_service(config, execution_context, monkeypatch)
        self._mock_app_schemas_response(
            httpx_mock,
            base_url,
            org,
            "my-app",
            [
                _make_deployed_app("my-app", "folder-a", "key-a"),
                _make_deployed_app("my-app", "folder-b", "key-b"),
            ],
        )
        self._mock_create_task_response(httpx_mock, base_url, org, tenant)

        task = tasks_service.create(
            title="Test",
            app_name="my-app",
            app_folder_path="folder-a",
        )

        assert isinstance(task, Task)

    def test_create_folder_path_takes_priority_over_folder_key(
        self,
        httpx_mock: HTTPXMock,
        config: UiPathApiConfig,
        execution_context: UiPathExecutionContext,
        monkeypatch: pytest.MonkeyPatch,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        monkeypatch.setenv("UIPATH_TENANT_ID", "test-tenant-id")
        tasks_service = self._make_tasks_service(config, execution_context, monkeypatch)
        self._mock_app_schemas_response(
            httpx_mock,
            base_url,
            org,
            "my-app",
            [
                _make_deployed_app("my-app", "folder-a", "key-a"),
                _make_deployed_app("my-app", "folder-b", "key-b"),
            ],
        )
        self._mock_create_task_response(httpx_mock, base_url, org, tenant)

        task = tasks_service.create(
            title="Test",
            app_name="my-app",
            app_folder_path="folder-a",
            app_folder_key="key-b",
        )

        assert isinstance(task, Task)

    def test_create_falls_back_to_env_folder_path(
        self,
        httpx_mock: HTTPXMock,
        config: UiPathApiConfig,
        execution_context: UiPathExecutionContext,
        monkeypatch: pytest.MonkeyPatch,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        monkeypatch.setenv("UIPATH_TENANT_ID", "test-tenant-id")
        tasks_service = self._make_tasks_service(
            config, execution_context, monkeypatch, folder_path="env-folder-path"
        )
        self._mock_app_schemas_response(
            httpx_mock,
            base_url,
            org,
            "my-app",
            [
                _make_deployed_app("my-app", "folder-a", "key-a"),
                _make_deployed_app(
                    "my-app", "env-folder-path", "key-b", system_name="my-app-b"
                ),
            ],
        )
        self._mock_create_task_response(httpx_mock, base_url, org, tenant)

        task = tasks_service.create(
            title="Test",
            app_name="my-app",
        )

        assert isinstance(task, Task)
        create_request = [
            r for r in httpx_mock.get_requests() if "CreateAppTask" in str(r.url)
        ][0]
        assert b"my-app-b" in create_request.content

    def test_create_falls_back_to_env_folder_key(
        self,
        httpx_mock: HTTPXMock,
        config: UiPathApiConfig,
        execution_context: UiPathExecutionContext,
        monkeypatch: pytest.MonkeyPatch,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        monkeypatch.setenv("UIPATH_TENANT_ID", "test-tenant-id")
        tasks_service = self._make_tasks_service(
            config, execution_context, monkeypatch, folder_key="env-key"
        )
        self._mock_app_schemas_response(
            httpx_mock,
            base_url,
            org,
            "my-app",
            [
                _make_deployed_app("my-app", "folder-a", "key-a"),
                _make_deployed_app("my-app", "folder-b", "env-key"),
            ],
        )
        self._mock_create_task_response(httpx_mock, base_url, org, tenant)

        task = tasks_service.create(
            title="Test",
            app_name="my-app",
        )

        assert isinstance(task, Task)

    def test_create_raises_when_app_not_found_in_tenant(
        self,
        httpx_mock: HTTPXMock,
        config: UiPathApiConfig,
        execution_context: UiPathExecutionContext,
        monkeypatch: pytest.MonkeyPatch,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        monkeypatch.setenv("UIPATH_TENANT_ID", "test-tenant-id")
        tasks_service = self._make_tasks_service(
            config, execution_context, monkeypatch, folder_path="folder-a"
        )
        self._mock_app_schemas_response(
            httpx_mock,
            base_url,
            org,
            "my-app",
            [_make_deployed_app("other-app", "folder-a", "key-a")],
        )

        with pytest.raises(
            Exception, match="'my-app' was not found in the current tenant"
        ):
            tasks_service.create(title="Test", app_name="my-app")

    def test_create_raises_when_app_not_found_in_folder_path(
        self,
        httpx_mock: HTTPXMock,
        config: UiPathApiConfig,
        execution_context: UiPathExecutionContext,
        monkeypatch: pytest.MonkeyPatch,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        monkeypatch.setenv("UIPATH_TENANT_ID", "test-tenant-id")
        tasks_service = self._make_tasks_service(config, execution_context, monkeypatch)
        self._mock_app_schemas_response(
            httpx_mock,
            base_url,
            org,
            "my-app",
            [_make_deployed_app("my-app", "folder-a", "key-a")],
        )

        with pytest.raises(
            Exception,
            match="'my-app' was not found in folder with fully qualified name 'folder-b'",
        ):
            tasks_service.create(
                title="Test", app_name="my-app", app_folder_path="folder-b"
            )

    def test_create_raises_when_app_not_found_in_folder_key(
        self,
        httpx_mock: HTTPXMock,
        config: UiPathApiConfig,
        execution_context: UiPathExecutionContext,
        monkeypatch: pytest.MonkeyPatch,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        monkeypatch.setenv("UIPATH_TENANT_ID", "test-tenant-id")
        tasks_service = self._make_tasks_service(config, execution_context, monkeypatch)
        self._mock_app_schemas_response(
            httpx_mock,
            base_url,
            org,
            "my-app",
            [_make_deployed_app("my-app", "folder-a", "key-a")],
        )

        with pytest.raises(
            Exception,
            match="'my-app' was not found in folder with identifier 'wrong-key'",
        ):
            tasks_service.create(
                title="Test",
                app_name="my-app",
                app_folder_key="wrong-key",
                app_folder_path=None,
            )

    def test_create_raises_when_no_folder_key_or_path_provided(
        self,
        httpx_mock: HTTPXMock,
        config: UiPathApiConfig,
        execution_context: UiPathExecutionContext,
        monkeypatch: pytest.MonkeyPatch,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        monkeypatch.setenv("UIPATH_TENANT_ID", "test-tenant-id")
        tasks_service = self._make_tasks_service(config, execution_context, monkeypatch)
        self._mock_app_schemas_response(
            httpx_mock,
            base_url,
            org,
            "my-app",
            [_make_deployed_app("my-app", "folder-a", "key-a")],
        )

        with pytest.raises(
            Exception, match="no folder key or folder path was provided"
        ):
            tasks_service.create(
                title="Test",
                app_name="my-app",
                app_folder_path=None,
            )
