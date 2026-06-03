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


# ---------------------------------------------------------------------------
# QuickForm task tests
# ---------------------------------------------------------------------------

_QF_SCHEMA: dict[str, Any] = {
    "id": "7ebef452-fee9-45df-8fc2-01f1d0248540",
    "fields": [
        {"id": "f1", "type": "text", "label": "F1", "direction": "input"},
        {"id": "f2", "type": "text", "label": "F2", "direction": "output"},
    ],
    "outcomes": [
        {"id": "approve", "name": "Approve", "type": "string", "isPrimary": True},
    ],
}
_QF_DEFAULTS = {
    "title": "QF task",
    "task_schema_key": _QF_SCHEMA["id"],
    "schema": _QF_SCHEMA,
}
_QF_CREATE_RESPONSE = {"id": 42, "title": _QF_DEFAULTS["title"]}


@pytest.fixture
def qf_create_url(base_url: str, org: str, tenant: str) -> str:
    return f"{base_url}{org}{tenant}/orchestrator_/tasks/GenericTasks/CreateTask"


@pytest.fixture
def qf_assign_url(base_url: str, org: str, tenant: str) -> str:
    return (
        f"{base_url}{org}{tenant}"
        "/orchestrator_/odata/Tasks/UiPath.Server.Configuration.OData.AssignTasks"
    )


def _posted_body(httpx_mock: HTTPXMock, url: str) -> dict[str, Any]:
    import json as _json

    for req in httpx_mock.get_requests():
        if str(req.url) == url:
            return _json.loads(req.content)
    raise AssertionError(f"no request was POSTed to {url}")


@pytest.fixture
def qf_runner(httpx_mock: HTTPXMock, service: TasksService, qf_create_url: str) -> Any:
    """Factory: stub the QF endpoint, call create_quickform with overrides,
    return (task, posted_body). One call per test eliminates setup duplication.
    """
    httpx_mock.add_response(
        url=qf_create_url, status_code=200, json=_QF_CREATE_RESPONSE
    )

    def _run(**overrides: Any) -> tuple[Task, dict[str, Any]]:
        task = service.create_quickform(**{**_QF_DEFAULTS, **overrides})
        return task, _posted_body(httpx_mock, qf_create_url)

    return _run


@pytest.fixture
def qf_runner_async(
    httpx_mock: HTTPXMock, service: TasksService, qf_create_url: str
) -> Any:
    """Async variant of qf_runner."""
    httpx_mock.add_response(
        url=qf_create_url, status_code=200, json=_QF_CREATE_RESPONSE
    )

    async def _run(**overrides: Any) -> tuple[Task, dict[str, Any]]:
        task = await service.create_quickform_async(**{**_QF_DEFAULTS, **overrides})
        return task, _posted_body(httpx_mock, qf_create_url)

    return _run


def test_create_quickform_baseline_payload(qf_runner: Any) -> None:
    task, body = qf_runner()
    assert body == {
        "type": 6,
        "taskSchemaKey": _QF_DEFAULTS["task_schema_key"],
        "schema": _QF_SCHEMA,
        "title": _QF_DEFAULTS["title"],
        "data": {},
    }
    assert isinstance(task, Task)
    assert task.id == 42


def test_create_quickform_data_passthrough(qf_runner: Any) -> None:
    _, body = qf_runner(data={"x": 1})
    assert body["data"] == {"x": 1}


def test_create_quickform_includes_optional_fields_when_set(qf_runner: Any) -> None:
    _, body = qf_runner(
        priority="High",
        labels=["a", "b"],
        is_actionable_message_enabled=True,
        actionable_message_metadata={"fieldSet": {}, "actionSet": {}},
        creator_job_key="3fa85f64-5717-4562-b3fc-2c963f66afa6",
    )
    assert body["priority"] == "High"
    assert {tag["name"] for tag in body["tags"]} == {"a", "b"}
    assert body["isActionableMessageEnabled"] is True
    assert body["actionableMessageMetaData"] == {"fieldSet": {}, "actionSet": {}}
    assert body["creatorJobKey"] == "3fa85f64-5717-4562-b3fc-2c963f66afa6"


def test_create_quickform_omits_optional_fields_when_unset(qf_runner: Any) -> None:
    _, body = qf_runner()
    for omitted in (
        "creatorJobKey",
        "priority",
        "tags",
        "isActionableMessageEnabled",
        "actionableMessageMetaData",
    ):
        assert omitted not in body


async def test_create_quickform_async_baseline_payload(qf_runner_async: Any) -> None:
    task, body = await qf_runner_async()
    assert body["type"] == 6
    assert body["taskSchemaKey"] == _QF_DEFAULTS["task_schema_key"]
    assert task.id == 42


def test_create_quickform_with_assignee_triggers_assign_call(
    httpx_mock: HTTPXMock, qf_runner: Any, qf_assign_url: str
) -> None:
    httpx_mock.add_response(url=qf_assign_url, status_code=200, json={})
    qf_runner(assignee="user@example.com")
    body = _posted_body(httpx_mock, qf_assign_url)
    assert body["taskAssignments"][0]["UserNameOrEmail"] == "user@example.com"


async def test_create_quickform_async_with_assignee_triggers_assign_call(
    httpx_mock: HTTPXMock, qf_runner_async: Any, qf_assign_url: str
) -> None:
    httpx_mock.add_response(url=qf_assign_url, status_code=200, json={})
    await qf_runner_async(assignee="user@example.com")
    body = _posted_body(httpx_mock, qf_assign_url)
    assert body["taskAssignments"][0]["UserNameOrEmail"] == "user@example.com"
