import uuid
from unittest.mock import AsyncMock, patch

import pytest
from pytest_httpx import HTTPXMock

from uipath._cli._runtime._contracts import (
    UiPathApiTrigger,
    UiPathResumeTrigger,
    UiPathResumeTriggerType,
    UiPathRuntimeError,
    UiPathRuntimeStatus,
)
from uipath._cli._runtime._hitl import HitlProcessor, HitlReader
from uipath.models import Action, CreateAction, InvokeProcess, Job, WaitAction, WaitJob
from uipath.models.job import JobErrorInfo


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
    async def test_read_action_trigger(
        self,
        setup_test_env: None,
    ) -> None:
        """Test reading an action trigger."""
        action_key = "test-action-key"
        action_data = {"answer": "test-action-data"}

        mock_action = Action(key=action_key, data=action_data)
        mock_retrieve_async = AsyncMock(return_value=mock_action)

        with patch(
            "uipath._services.actions_service.ActionsService.retrieve_async",
            new=mock_retrieve_async,
        ):
            resume_trigger = UiPathResumeTrigger(
                trigger_type=UiPathResumeTriggerType.ACTION,
                item_key=action_key,
                folder_key="test-folder",
                folder_path="test-path",
            )

            result = await HitlReader.read(resume_trigger)
            assert result == action_data
            mock_retrieve_async.assert_called_once_with(
                action_key, app_folder_key="test-folder", app_folder_path="test-path"
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
            "uipath._services.jobs_service.JobsService.retrieve_async",
            new=mock_retrieve_async,
        ):
            resume_trigger = UiPathResumeTrigger(
                trigger_type=UiPathResumeTriggerType.JOB,
                item_key=job_key,
                folder_key="test-folder",
                folder_path="test-path",
            )

            result = await HitlReader.read(resume_trigger)
            assert result == output_args
            mock_retrieve_async.assert_called_once_with(
                job_key, folder_key="test-folder", folder_path="test-path"
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

        mock_job = Job(id=job_id, key=job_key, state="Failed", job_error=job_error_info)
        mock_retrieve_async = AsyncMock(return_value=mock_job)

        with patch(
            "uipath._services.jobs_service.JobsService.retrieve_async",
            new=mock_retrieve_async,
        ):
            resume_trigger = UiPathResumeTrigger(
                trigger_type=UiPathResumeTriggerType.JOB,
                item_key=job_key,
                folder_key="test-folder",
                folder_path="test-path",
            )

            with pytest.raises(UiPathRuntimeError) as exc_info:
                await HitlReader.read(resume_trigger)
            error_dict = exc_info.value.as_dict
            assert error_dict["code"] == "Python.INVOKED_PROCESS_FAILURE"
            assert error_dict["title"] == "Invoked process did not finish successfully."
            assert job_error_info.code in error_dict["detail"]
            mock_retrieve_async.assert_called_once_with(
                job_key, folder_key="test-folder", folder_path="test-path"
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

        result = await HitlReader.read(resume_trigger)
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

        with pytest.raises(UiPathRuntimeError) as exc_info:
            await HitlReader.read(resume_trigger)
        error_dict = exc_info.value.as_dict
        assert error_dict["code"] == "Python.API_CONNECTION_ERROR"
        assert error_dict["title"] == "Failed to get trigger payload"
        assert "Server error '500 Internal Server Error'" in error_dict["detail"]


class TestHitlProcessor:
    """Tests for the HitlProcessor class."""

    @pytest.mark.anyio
    async def test_create_resume_trigger_create_action(
        self,
        setup_test_env: None,
    ) -> None:
        """Test creating a resume trigger for CreateAction."""
        action_key = "test-action-key"
        create_action = CreateAction(
            title="Test Action",
            app_name="TestApp",
            app_folder_path="/test/path",
            data={"input": "test-input"},
        )

        mock_action = Action(key=action_key)
        mock_create_async = AsyncMock(return_value=mock_action)

        with patch(
            "uipath._services.actions_service.ActionsService.create_async",
            new=mock_create_async,
        ):
            processor = HitlProcessor(create_action)
            resume_trigger = await processor.create_resume_trigger()

            assert resume_trigger is not None
            assert resume_trigger.trigger_type == UiPathResumeTriggerType.ACTION
            assert resume_trigger.item_key == action_key
            assert resume_trigger.folder_path == create_action.app_folder_path
            mock_create_async.assert_called_once_with(
                title=create_action.title,
                app_name=create_action.app_name,
                app_folder_path=create_action.app_folder_path,
                app_folder_key="",
                app_key="",
                app_version=1,
                assignee="",
                data=create_action.data,
            )

    @pytest.mark.anyio
    async def test_create_resume_trigger_wait_action(
        self,
        setup_test_env: None,
    ) -> None:
        """Test creating a resume trigger for WaitAction."""
        action_key = "test-action-key"
        action = Action(key=action_key)
        wait_action = WaitAction(action=action, app_folder_path="/test/path")

        processor = HitlProcessor(wait_action)
        resume_trigger = await processor.create_resume_trigger()

        assert resume_trigger is not None
        assert resume_trigger.trigger_type == UiPathResumeTriggerType.ACTION
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
            "uipath._services.processes_service.ProcessesService.invoke_async",
            new=mock_invoke,
        ) as mock_process_invoke_async:
            processor = HitlProcessor(invoke_process)
            resume_trigger = await processor.create_resume_trigger()

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

        processor = HitlProcessor(wait_job)
        resume_trigger = await processor.create_resume_trigger()

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

        processor = HitlProcessor(api_input)
        resume_trigger = await processor.create_resume_trigger()

        assert resume_trigger is not None
        assert resume_trigger.trigger_type == UiPathResumeTriggerType.API
        assert resume_trigger.api_resume is not None
        assert isinstance(resume_trigger.api_resume.inbox_id, str)
        assert resume_trigger.api_resume.request == api_input
