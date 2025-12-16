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
from uipath.platform.common import (
    CreateBatchTransform,
    CreateDeepRag,
    CreateTask,
    InvokeProcess,
    WaitBatchTransform,
    WaitDeepRag,
    WaitJob,
    WaitTask,
)
from uipath.platform.context_grounding import (
    BatchTransformCreationResponse,
    BatchTransformOutputColumn,
    Citation,
    CitationMode,
    DeepRagCreationResponse,
    DeepRagStatus,
)
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

    @pytest.mark.anyio
    async def test_read_deep_rag_trigger_successful(
        self,
        setup_test_env: None,
    ) -> None:
        """Test reading a successful deep rag trigger."""
        from uipath.platform.context_grounding import DeepRagResponse
        from uipath.platform.context_grounding.context_grounding import DeepRagContent

        task_id = "test-deep-rag-id"
        content = DeepRagContent(
            text="test content",
            citations=[
                Citation(
                    ordinal=1, page_number=1, source="source", reference="reference"
                )
            ],
        )
        mock_deep_rag = DeepRagResponse(
            name="test-deep-rag",
            created_date="2024-01-01",
            last_deep_rag_status=DeepRagStatus.SUCCESSFUL,
            content=content,
        )
        mock_retrieve_async = AsyncMock(return_value=mock_deep_rag)

        with patch(
            "uipath.platform.context_grounding._context_grounding_service.ContextGroundingService.retrieve_deep_rag_async",
            new=mock_retrieve_async,
        ):
            resume_trigger = UiPathResumeTrigger(
                trigger_type=UiPathResumeTriggerType.DEEP_RAG,
                item_key=task_id,
                folder_key="test-folder",
                folder_path="test-path",
                payload={"index_name": "test-index"},
            )
            reader = UiPathResumeTriggerReader()
            result = await reader.read_trigger(resume_trigger)
            assert result == content.model_dump()
            mock_retrieve_async.assert_called_once_with(
                task_id,
                index_name="test-index",
            )

    @pytest.mark.anyio
    async def test_read_deep_rag_trigger_pending(
        self,
        setup_test_env: None,
    ) -> None:
        """Test reading a pending deep rag trigger raises pending error."""
        from uipath.core.errors import UiPathPendingTriggerError

        from uipath.platform.context_grounding import DeepRagResponse

        task_id = "test-deep-rag-id"
        mock_deep_rag = DeepRagResponse(
            name="test-deep-rag",
            created_date="2024-01-01",
            last_deep_rag_status=DeepRagStatus.QUEUED,
            content=None,
        )
        mock_retrieve_async = AsyncMock(return_value=mock_deep_rag)

        with patch(
            "uipath.platform.context_grounding._context_grounding_service.ContextGroundingService.retrieve_deep_rag_async",
            new=mock_retrieve_async,
        ):
            resume_trigger = UiPathResumeTrigger(
                trigger_type=UiPathResumeTriggerType.DEEP_RAG,
                item_key=task_id,
                folder_key="test-folder",
                folder_path="test-path",
            )

            with pytest.raises(UiPathPendingTriggerError):
                reader = UiPathResumeTriggerReader()
                await reader.read_trigger(resume_trigger)

    @pytest.mark.anyio
    async def test_read_deep_rag_trigger_failed(
        self,
        setup_test_env: None,
    ) -> None:
        """Test reading a failed deep rag trigger raises faulted error."""
        from uipath.platform.context_grounding import DeepRagResponse

        task_id = "test-deep-rag-id"
        mock_deep_rag = DeepRagResponse(
            name="test-deep-rag",
            created_date="2024-01-01",
            last_deep_rag_status=DeepRagStatus.FAILED,
            content=None,
        )
        mock_retrieve_async = AsyncMock(return_value=mock_deep_rag)

        with patch(
            "uipath.platform.context_grounding._context_grounding_service.ContextGroundingService.retrieve_deep_rag_async",
            new=mock_retrieve_async,
        ):
            resume_trigger = UiPathResumeTrigger(
                trigger_type=UiPathResumeTriggerType.DEEP_RAG,
                item_key=task_id,
                folder_key="test-folder",
                folder_path="test-path",
            )

            with pytest.raises(UiPathFaultedTriggerError) as exc_info:
                reader = UiPathResumeTriggerReader()
                await reader.read_trigger(resume_trigger)
            assert exc_info.value.args[0] == ErrorCategory.USER

    @pytest.mark.anyio
    async def test_read_deep_rag_trigger_empty_response(
        self,
        setup_test_env: None,
    ) -> None:
        """Test reading a deep rag trigger with empty content returns placeholder."""
        from uipath.platform.context_grounding import DeepRagResponse

        task_id = "test-deep-rag-id"
        mock_deep_rag = DeepRagResponse(
            name="test-deep-rag",
            created_date="2024-01-01",
            last_deep_rag_status=DeepRagStatus.SUCCESSFUL,
            content=None,
        )
        mock_retrieve_async = AsyncMock(return_value=mock_deep_rag)

        with patch(
            "uipath.platform.context_grounding._context_grounding_service.ContextGroundingService.retrieve_deep_rag_async",
            new=mock_retrieve_async,
        ):
            resume_trigger = UiPathResumeTrigger(
                trigger_type=UiPathResumeTriggerType.DEEP_RAG,
                item_key=task_id,
                folder_key="test-folder",
                folder_path="test-path",
            )
            reader = UiPathResumeTriggerReader()
            result = await reader.read_trigger(resume_trigger)
            assert result == {
                "status": DeepRagStatus.SUCCESSFUL.value,
                PropertyName.INTERNAL.value: TriggerMarker.NO_CONTENT.value,
            }

    @pytest.mark.anyio
    async def test_read_batch_rag_trigger_successful(
        self,
        setup_test_env: None,
    ) -> None:
        """Test reading a successful batch rag trigger."""
        import os

        task_id = "test-batch-rag-id"
        destination_path = "test/output.xlsx"
        mock_download_async = AsyncMock(return_value=None)

        with patch(
            "uipath.platform.context_grounding._context_grounding_service.ContextGroundingService.download_batch_transform_result_async",
            new=mock_download_async,
        ):
            resume_trigger = UiPathResumeTrigger(
                trigger_type=UiPathResumeTriggerType.BATCH_RAG,
                item_key=task_id,
                folder_key="test-folder",
                folder_path="test-path",
                payload={
                    "index_name": "test-index",
                    "destination_path": destination_path,
                },
            )
            reader = UiPathResumeTriggerReader()
            result = await reader.read_trigger(resume_trigger)
            assert (
                result
                == f"Batch transform completed. Modified file available at {os.path.abspath(destination_path)}"
            )
            mock_download_async.assert_called_once_with(
                task_id,
                destination_path,
                validate_status=True,
                index_name="test-index",
            )

    @pytest.mark.anyio
    async def test_read_batch_rag_trigger_pending(
        self,
        setup_test_env: None,
    ) -> None:
        """Test reading a pending batch rag trigger raises pending error."""
        from uipath.core.errors import UiPathPendingTriggerError

        from uipath.platform.errors import BatchTransformNotCompleteException

        task_id = "test-batch-rag-id"
        destination_path = "test/output.xlsx"
        mock_download_async = AsyncMock(
            side_effect=BatchTransformNotCompleteException(task_id, "InProgress")
        )

        with patch(
            "uipath.platform.context_grounding._context_grounding_service.ContextGroundingService.download_batch_transform_result_async",
            new=mock_download_async,
        ):
            resume_trigger = UiPathResumeTrigger(
                trigger_type=UiPathResumeTriggerType.BATCH_RAG,
                item_key=task_id,
                folder_key="test-folder",
                folder_path="test-path",
                payload={
                    "index_name": "test-index",
                    "destination_path": destination_path,
                },
            )

            with pytest.raises(UiPathPendingTriggerError):
                reader = UiPathResumeTriggerReader()
                await reader.read_trigger(resume_trigger)


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

    @pytest.mark.anyio
    async def test_create_resume_trigger_create_deep_rag(
        self,
        setup_test_env: None,
    ) -> None:
        """Test creating a resume trigger for CreateDeepRag."""
        deep_rag_id = "test-deep-rag-id"
        create_deep_rag = CreateDeepRag(
            name="test-deep-rag",
            index_name="test-index",
            prompt="test prompt",
            glob_pattern="**/*.pdf",
            citation_mode=CitationMode.INLINE,
            index_folder_path="/test/path",
        )

        mock_deep_rag = DeepRagCreationResponse(
            id=deep_rag_id,
            last_deep_rag_status=DeepRagStatus.QUEUED,
            created_date="2024-01-01",
        )
        mock_start_deep_rag_async = AsyncMock(return_value=mock_deep_rag)

        with patch(
            "uipath.platform.context_grounding._context_grounding_service.ContextGroundingService.start_deep_rag_async",
            new=mock_start_deep_rag_async,
        ):
            processor = UiPathResumeTriggerCreator()
            resume_trigger = await processor.create_trigger(create_deep_rag)

            assert resume_trigger is not None
            assert resume_trigger.trigger_type == UiPathResumeTriggerType.DEEP_RAG
            assert resume_trigger.item_key == deep_rag_id
            mock_start_deep_rag_async.assert_called_once_with(
                name=create_deep_rag.name,
                index_name=create_deep_rag.index_name,
                prompt=create_deep_rag.prompt,
                glob_pattern=create_deep_rag.glob_pattern,
                citation_mode=create_deep_rag.citation_mode,
                folder_path=create_deep_rag.index_folder_path,
                folder_key=create_deep_rag.index_folder_key,
            )

    @pytest.mark.anyio
    async def test_create_resume_trigger_wait_deep_rag(
        self,
        setup_test_env: None,
    ) -> None:
        """Test creating a resume trigger for WaitDeepRag."""
        deep_rag_id = "test-deep-rag-id"
        deep_rag = DeepRagCreationResponse(
            id=deep_rag_id,
            last_deep_rag_status=DeepRagStatus.IN_PROGRESS,
            created_date="2024-01-01",
        )
        wait_deep_rag = WaitDeepRag(deep_rag=deep_rag, index_folder_path="/test/path")

        processor = UiPathResumeTriggerCreator()
        resume_trigger = await processor.create_trigger(wait_deep_rag)

        assert resume_trigger is not None
        assert resume_trigger.trigger_type == UiPathResumeTriggerType.DEEP_RAG
        assert resume_trigger.item_key == deep_rag_id

    @pytest.mark.anyio
    async def test_create_resume_trigger_create_batch_transform(
        self,
        setup_test_env: None,
    ) -> None:
        """Test creating a resume trigger for CreateBatchTransform."""
        batch_transform_id = "test-batch-transform-id"
        output_columns = [
            BatchTransformOutputColumn(name="column1", description="desc1"),
        ]
        create_batch_transform = CreateBatchTransform(
            name="test-batch-transform",
            index_name="test-index",
            prompt="test prompt",
            output_columns=output_columns,
            destination_path="/output/path.xlsx",
            index_folder_path="/test/path",
        )

        mock_batch_transform = BatchTransformCreationResponse(
            id=batch_transform_id,
            last_batch_rag_status=DeepRagStatus.QUEUED,
        )
        mock_start_batch_transform = AsyncMock(return_value=mock_batch_transform)

        with patch(
            "uipath.platform.context_grounding._context_grounding_service.ContextGroundingService.start_batch_transform_async",
            new=mock_start_batch_transform,
        ):
            processor = UiPathResumeTriggerCreator()
            resume_trigger = await processor.create_trigger(create_batch_transform)

            assert resume_trigger is not None
            assert resume_trigger.trigger_type == UiPathResumeTriggerType.BATCH_RAG
            assert resume_trigger.item_key == batch_transform_id
            mock_start_batch_transform.assert_called_once_with(
                name=create_batch_transform.name,
                index_name=create_batch_transform.index_name,
                prompt=create_batch_transform.prompt,
                output_columns=create_batch_transform.output_columns,
                storage_bucket_folder_path_prefix=create_batch_transform.storage_bucket_folder_path_prefix,
                enable_web_search_grounding=create_batch_transform.enable_web_search_grounding,
                folder_path=create_batch_transform.index_folder_path,
                folder_key=create_batch_transform.index_folder_key,
            )

    @pytest.mark.anyio
    async def test_create_resume_trigger_wait_batch_transform(
        self,
        setup_test_env: None,
    ) -> None:
        """Test creating a resume trigger for WaitBatchTransform."""
        batch_transform_id = "test-batch-transform-id"
        batch_transform = BatchTransformCreationResponse(
            id=batch_transform_id,
            last_batch_rag_status=DeepRagStatus.IN_PROGRESS,
        )
        wait_batch_transform = WaitBatchTransform(
            batch_transform=batch_transform, index_folder_path="/test/path"
        )

        processor = UiPathResumeTriggerCreator()
        resume_trigger = await processor.create_trigger(wait_batch_transform)

        assert resume_trigger is not None
        assert resume_trigger.trigger_type == UiPathResumeTriggerType.BATCH_RAG
        assert resume_trigger.item_key == batch_transform_id
