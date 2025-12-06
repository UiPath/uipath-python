import uuid
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pytest_httpx import HTTPXMock
from uipath.core.errors import ErrorCategory, UiPathFaultedTriggerError
from uipath.runtime import (
    UiPathApiTrigger,
    UiPathResumeTrigger,
    UiPathResumeTriggerType,
    UiPathRuntimeStatus,
)

from uipath.platform.action_center import Task
from uipath.platform.action_center.tasks import TaskStatus
from uipath.platform.common import CreateTask, InvokeProcess, WaitJob, WaitTask
from uipath.platform.orchestrator import (
    Job,
    JobErrorInfo,
)
from uipath.platform.resume_triggers import (
    PropertyName,
    TriggerMarker,
    UiPathResumeTriggerCreator,
    UiPathResumeTriggerReader,
)


@pytest.fixture
def base_url(mock_env_vars: dict[str, str]) -> str:
    return mock_env_vars["UIPATH_URL"]


@pytest.fixture
def setup_test_env(
    monkeypatch: pytest.MonkeyPatch, mock_env_vars: dict[str, str]
) -> None:
    """Setup test environment variables."""
    for key, value in mock_env_vars.items():
        monkeypatch.setenv(key, value)


class TestHitlReader:
    """Tests for the HitlReader class."""

    @pytest.mark.anyio
    async def test_read_task_trigger(
        self,
        setup_test_env: None,
    ) -> None:
        """Test reading an action trigger."""
        action_key = "test-action-key"
        action_data = {"answer": "test-action-data"}

        mock_action = Task(key=action_key, data=action_data)
        mock_retrieve_async = AsyncMock(return_value=mock_action)

        with patch(
            "uipath.platform.action_center._tasks_service.TasksService.retrieve_async",
            new=mock_retrieve_async,
        ):
            resume_trigger = UiPathResumeTrigger(
                trigger_type=UiPathResumeTriggerType.TASK,
                item_key=action_key,
                folder_key="test-folder",
                folder_path="test-path",
            )
            reader = UiPathResumeTriggerReader()
            result = await reader.read_trigger(resume_trigger)
            assert result == action_data
            mock_retrieve_async.assert_called_once_with(
                action_key,
                app_folder_key="test-folder",
                app_folder_path="test-path",
                app_name=None,
            )

    @pytest.mark.anyio
    async def test_read_task_trigger_empty_response(
        self,
        setup_test_env: None,
    ) -> None:
        """Test reading an action trigger."""
        action_key = "test-action-key"
        action_data: dict[str, Any] = {}

        mock_task = Task(key=action_key, data=action_data, status=2)
        mock_retrieve_async = AsyncMock(return_value=mock_task)

        with patch(
            "uipath.platform.action_center._tasks_service.TasksService.retrieve_async",
            new=mock_retrieve_async,
        ):
            resume_trigger = UiPathResumeTrigger(
                trigger_type=UiPathResumeTriggerType.TASK,
                item_key=action_key,
                folder_key="test-folder",
                folder_path="test-path",
            )
            reader = UiPathResumeTriggerReader()
            result = await reader.read_trigger(resume_trigger)
            assert result == {
                "status": TaskStatus(2).name.lower(),
                PropertyName.INTERNAL.value: TriggerMarker.NO_CONTENT.value,
            }
            mock_retrieve_async.assert_called_once_with(
                action_key,
                app_folder_key="test-folder",
                app_folder_path="test-path",
                app_name=None,
            )

    @pytest.mark.anyio
    async def test_read_job_trigger_successful(
        self,
        setup_test_env: None,
    ) -> None:
        """Test reading a successful job trigger."""
        job_key = "test-job-key"
        job_id = 1234
        output_args = str({"result": "success"})

        mock_job = Job(
            id=job_id,
            key=job_key,
            state=UiPathRuntimeStatus.SUCCESSFUL.value,
            output_arguments=output_args,
        )
        mock_retrieve_async = AsyncMock(return_value=mock_job)

        with patch(
            "uipath.platform.orchestrator._jobs_service.JobsService.retrieve_async",
            new=mock_retrieve_async,
        ):
            resume_trigger = UiPathResumeTrigger(
                trigger_type=UiPathResumeTriggerType.JOB,
                item_key=job_key,
                folder_key="test-folder",
                folder_path="test-path",
            )
            reader = UiPathResumeTriggerReader()
            result = await reader.read_trigger(resume_trigger)
            assert result == output_args
            mock_retrieve_async.assert_called_once_with(
                job_key,
                folder_key="test-folder",
                folder_path="test-path",
                process_name=None,
            )

    @pytest.mark.anyio
    async def test_read_job_trigger_successful_empty_output(
        self,
        setup_test_env: None,
    ) -> None:
        """Test reading a successful job trigger with empty output returns job state."""
        job_key = "test-job-key"
        job_id = 1234
        job_state = UiPathRuntimeStatus.SUCCESSFUL.value

        mock_job = Job(
            id=job_id,
            key=job_key,
            state=job_state,
            output_arguments="{}",
        )
        mock_retrieve_async = AsyncMock(return_value=mock_job)

        with patch(
            "uipath.platform.orchestrator._jobs_service.JobsService.retrieve_async",
            new=mock_retrieve_async,
        ):
            resume_trigger = UiPathResumeTrigger(
                trigger_type=UiPathResumeTriggerType.JOB,
                item_key=job_key,
                folder_key="test-folder",
                folder_path="test-path",
            )
            reader = UiPathResumeTriggerReader()
            result = await reader.read_trigger(resume_trigger)
            assert result == {
                "state": job_state.lower(),
                PropertyName.INTERNAL.value: TriggerMarker.NO_CONTENT.value,
            }
            mock_retrieve_async.assert_called_once_with(
                job_key,
                folder_key="test-folder",
                folder_path="test-path",
                process_name=None,
            )

    @pytest.mark.anyio
    async def test_read_job_trigger_failed(
        self,
        setup_test_env: None,
    ) -> None:
        """Test reading a failed job trigger."""
        job_key = "test-job-key"
        job_error_info = JobErrorInfo(code="error code")
        job_id = 1234

        mock_job = Job(
            id=job_id, key=job_key, state="Faulted", job_error=job_error_info
        )
        mock_retrieve_async = AsyncMock(return_value=mock_job)

        with patch(
            "uipath.platform.orchestrator._jobs_service.JobsService.retrieve_async",
            new=mock_retrieve_async,
        ):
            resume_trigger = UiPathResumeTrigger(
                trigger_type=UiPathResumeTriggerType.JOB,
                item_key=job_key,
                folder_key="test-folder",
                folder_path="test-path",
                payload={"name": "process_name"},
            )

            with pytest.raises(UiPathFaultedTriggerError) as exc_info:
                reader = UiPathResumeTriggerReader()
                await reader.read_trigger(resume_trigger)
            assert exc_info.value.args[0] == ErrorCategory.USER
            mock_retrieve_async.assert_called_once_with(
                job_key,
                folder_key="test-folder",
                folder_path="test-path",
                process_name="process_name",
            )

    @pytest.mark.anyio
    async def test_read_api_trigger(
        self,
        httpx_mock: HTTPXMock,
        base_url: str,
        setup_test_env: None,
    ) -> None:
        """Test reading an API trigger."""
        inbox_id = str(uuid.uuid4())
        payload_data = {"key": "value"}

        httpx_mock.add_response(
            url=f"{base_url}/orchestrator_/api/JobTriggers/GetPayload/{inbox_id}",
            status_code=200,
            json={"payload": payload_data},
        )

        resume_trigger = UiPathResumeTrigger(
            trigger_type=UiPathResumeTriggerType.API,
            api_resume=UiPathApiTrigger(inbox_id=inbox_id, request="test"),
        )

        reader = UiPathResumeTriggerReader()
        result = await reader.read_trigger(resume_trigger)
        assert result == payload_data

    @pytest.mark.anyio
    async def test_read_api_trigger_failure(
        self,
        httpx_mock: HTTPXMock,
        base_url: str,
        setup_test_env: None,
    ) -> None:
        """Test reading an API trigger with a failed response."""
        inbox_id = str(uuid.uuid4())

        httpx_mock.add_response(
            url=f"{base_url}/orchestrator_/api/JobTriggers/GetPayload/{inbox_id}",
            status_code=500,
        )

        resume_trigger = UiPathResumeTrigger(
            trigger_type=UiPathResumeTriggerType.API,
            api_resume=UiPathApiTrigger(inbox_id=inbox_id, request="test"),
        )

        with pytest.raises(UiPathFaultedTriggerError) as exc_info:
            reader = UiPathResumeTriggerReader()
            await reader.read_trigger(resume_trigger)
        assert exc_info.value.args[0] == ErrorCategory.SYSTEM


class TestHitlProcessor:
    """Tests for the HitlProcessor class."""

    @pytest.mark.anyio
    async def test_create_resume_trigger_create_task(
        self,
        setup_test_env: None,
    ) -> None:
        """Test creating a resume trigger for CreateTask."""
        action_key = "test-action-key"
        create_action = CreateTask(
            title="Test Action",
            app_name="TestApp",
            app_folder_path="/test/path",
            data={"input": "test-input"},
        )

        mock_action = Task(key=action_key)
        mock_create_async = AsyncMock(return_value=mock_action)

        with patch(
            "uipath.platform.action_center._tasks_service.TasksService.create_async",
            new=mock_create_async,
        ):
            processor = UiPathResumeTriggerCreator()
            resume_trigger = await processor.create_trigger(create_action)

            assert resume_trigger is not None
            assert resume_trigger.trigger_type == UiPathResumeTriggerType.TASK
            assert resume_trigger.item_key == action_key
            assert resume_trigger.folder_path == create_action.app_folder_path
            mock_create_async.assert_called_once_with(
                title=create_action.title,
                app_name=create_action.app_name,
                app_folder_path=create_action.app_folder_path,
                app_folder_key="",
                app_key="",
                assignee="",
                data=create_action.data,
            )

    @pytest.mark.anyio
    async def test_create_resume_trigger_wait_task(
        self,
        setup_test_env: None,
    ) -> None:
        """Test creating a resume trigger for WaitTask."""
        action_key = "test-action-key"
        action = Task(key=action_key)
        wait_action = WaitTask(action=action, app_folder_path="/test/path")

        processor = UiPathResumeTriggerCreator()
        resume_trigger = await processor.create_trigger(wait_action)

        assert resume_trigger is not None
        assert resume_trigger.trigger_type == UiPathResumeTriggerType.TASK
        assert resume_trigger.item_key == action_key
        assert resume_trigger.folder_path == wait_action.app_folder_path

    @pytest.mark.anyio
    async def test_create_resume_trigger_invoke_process(
        self,
        setup_test_env: None,
    ) -> None:
        """Test creating a resume trigger for InvokeProcess."""
        job_key = "test-job-key"
        invoke_process = InvokeProcess(
            name="TestProcess",
            process_folder_path="/test/path",
            input_arguments={"key": "value"},
        )

        mock_job = Job(id=1234, key=job_key)
        mock_invoke = AsyncMock(return_value=mock_job)

        with patch(
            "uipath.platform.orchestrator._processes_service.ProcessesService.invoke_async",
            new=mock_invoke,
        ) as mock_process_invoke_async:
            processor = UiPathResumeTriggerCreator()
            resume_trigger = await processor.create_trigger(invoke_process)

            assert resume_trigger is not None
            assert resume_trigger.trigger_type == UiPathResumeTriggerType.JOB
            assert resume_trigger.item_key == job_key
            assert resume_trigger.folder_path == invoke_process.process_folder_path
            mock_process_invoke_async.assert_called_once_with(
                name=invoke_process.name,
                input_arguments=invoke_process.input_arguments,
                folder_path=invoke_process.process_folder_path,
                folder_key=None,
            )

    @pytest.mark.anyio
    async def test_create_resume_trigger_wait_job(
        self,
        setup_test_env: None,
    ) -> None:
        """Test creating a resume trigger for WaitJob."""
        job_key = "test-job-key"
        job = Job(id=1234, key=job_key)
        wait_job = WaitJob(job=job, process_folder_path="/test/path")

        processor = UiPathResumeTriggerCreator()
        resume_trigger = await processor.create_trigger(wait_job)

        assert resume_trigger is not None
        assert resume_trigger.trigger_type == UiPathResumeTriggerType.JOB
        assert resume_trigger.item_key == job_key
        assert resume_trigger.folder_path == wait_job.process_folder_path

    @pytest.mark.anyio
    async def test_create_resume_trigger_api(
        self,
        setup_test_env: None,
    ) -> None:
        """Test creating a resume trigger for API type."""
        api_input = "payload"

        processor = UiPathResumeTriggerCreator()
        resume_trigger = await processor.create_trigger(api_input)

        assert resume_trigger is not None
        assert resume_trigger.trigger_type == UiPathResumeTriggerType.API
        assert resume_trigger.api_resume is not None
        assert isinstance(resume_trigger.api_resume.inbox_id, str)
        assert resume_trigger.api_resume.request == api_input
