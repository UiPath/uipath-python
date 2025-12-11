"""Implementation of UiPath resume trigger protocols."""

import json
import os
import uuid
from typing import Any

from uipath.core.errors import (
    ErrorCategory,
    UiPathFaultedTriggerError,
    UiPathPendingTriggerError,
)
from uipath.runtime import (
    UiPathApiTrigger,
    UiPathResumeTrigger,
    UiPathResumeTriggerName,
    UiPathResumeTriggerType,
)

from uipath._cli._utils._common import serialize_object
from uipath.platform import UiPath
from uipath.platform.action_center import Task
from uipath.platform.action_center.tasks import TaskStatus
from uipath.platform.common import (
    CreateBatchTransform,
    CreateDeepRag,
    CreateEscalation,
    CreateTask,
    InvokeProcess,
    WaitBatchTransform,
    WaitDeepRag,
    WaitEscalation,
    WaitJob,
    WaitTask,
)
from uipath.platform.context_grounding import DeepRagStatus
from uipath.platform.errors import BatchTransformNotCompleteException
from uipath.platform.orchestrator.job import JobState
from uipath.platform.resume_triggers._enums import PropertyName, TriggerMarker


def _try_convert_to_json_format(value: str | None) -> Any:
    """Attempts to parse a string as JSON and returns the parsed object or original string.

    Args:
        value: The string value to attempt JSON parsing on.

    Returns:
        The parsed JSON object if successful, otherwise the original string value.
    """
    try:
        if not value:
            return None
        return json.loads(value)
    except json.decoder.JSONDecodeError:
        return value


class UiPathResumeTriggerReader:
    """Handles reading and retrieving Human-In-The-Loop (HITL) data from UiPath services.

    Implements UiPathResumeTriggerReaderProtocol.
    """

    def _extract_field(self, field_name: str, payload: Any) -> str | None:
        """Extracts a field from the payload and returns it if it exists."""
        if not payload:
            return payload

        if isinstance(payload, dict):
            return payload.get(field_name)

        # 2.3.0 remove
        try:
            payload_dict = json.loads(payload)
            return payload_dict.get(field_name)
        except json.decoder.JSONDecodeError:
            return None

    async def read_trigger(self, trigger: UiPathResumeTrigger) -> Any | None:
        """Read a resume trigger and convert it to runtime-compatible input.

        This method retrieves data from UiPath services (Actions, Jobs, API)
        based on the trigger type and returns it in a format that the
        runtime can use to resume execution.

        Args:
            trigger: The resume trigger to read

        Returns:
            The data retrieved from UiPath services, ready to be used
            as resume input. Format depends on trigger type:
            - TASK: Task data (possibly with escalation processing)
            - JOB: Job output data
            - API: API payload
            Returns None if no data is available.

        Raises:
            UiPathRuntimeError: If reading fails, job failed, API connection failed,
                trigger type is unknown, or HITL feedback retrieval failed.
        """
        uipath = UiPath()

        match trigger.trigger_type:
            case UiPathResumeTriggerType.TASK:
                if trigger.item_key:
                    task: Task = await uipath.tasks.retrieve_async(
                        trigger.item_key,
                        app_folder_key=trigger.folder_key,
                        app_folder_path=trigger.folder_path,
                        app_name=self._extract_field("app_name", trigger.payload),
                    )
                    pending_status = TaskStatus.PENDING.value
                    unassigned_status = TaskStatus.UNASSIGNED.value

                    if task.status in (pending_status, unassigned_status):
                        # 2.3.0 remove (task.status will already be the enum)
                        current_status = (
                            TaskStatus(task.status).name
                            if isinstance(task.status, int)
                            else "Unknown"
                        )
                        raise UiPathPendingTriggerError(
                            ErrorCategory.SYSTEM,
                            f"Task is not completed yet. Current status: {current_status}",
                        )

                    if trigger.trigger_name == UiPathResumeTriggerName.ESCALATION:
                        return task

                    trigger_response = task.data
                    if not bool(trigger_response):
                        # 2.3.0 change to task.status.name
                        assert isinstance(task.status, int)
                        trigger_response = {
                            "status": TaskStatus(task.status).name.lower(),
                            PropertyName.INTERNAL.value: TriggerMarker.NO_CONTENT.value,
                        }

                    return trigger_response

            case UiPathResumeTriggerType.JOB:
                if trigger.item_key:
                    job = await uipath.jobs.retrieve_async(
                        trigger.item_key,
                        folder_key=trigger.folder_key,
                        folder_path=trigger.folder_path,
                        process_name=self._extract_field("name", trigger.payload),
                    )
                    job_state = (job.state or "").lower()
                    successful_state = JobState.SUCCESSFUL.value
                    faulted_state = JobState.FAULTED.value
                    running_state = JobState.RUNNING.value
                    pending_state = JobState.PENDING.value

                    if job_state in (pending_state, running_state):
                        raise UiPathPendingTriggerError(
                            ErrorCategory.SYSTEM,
                            f"Job is not finished yet. Current state: {job_state}",
                        )

                    if job_state != successful_state:
                        job_error = (
                            _try_convert_to_json_format(str(job.job_error or job.info))
                            or "Job error unavailable."
                            if job_state == faulted_state
                            else f"Job {job.key} is {job_state}."
                        )
                        raise UiPathFaultedTriggerError(
                            ErrorCategory.USER,
                            f"Process did not finish successfully. Error: {job_error}",
                        )

                    output_data = await uipath.jobs.extract_output_async(job)
                    trigger_response = _try_convert_to_json_format(output_data)

                    # if response is an empty dictionary, use job state as placeholder value
                    if isinstance(trigger_response, dict) and not bool(
                        trigger_response
                    ):
                        # 2.3.0 change to job_state.value
                        trigger_response = {
                            "state": job_state,
                            PropertyName.INTERNAL.value: TriggerMarker.NO_CONTENT.value,
                        }

                    return trigger_response
            case UiPathResumeTriggerType.DEEP_RAG:
                if trigger.item_key:
                    deep_rag = await uipath.context_grounding.retrieve_deep_rag_async(
                        trigger.item_key,
                        index_name=self._extract_field("index_name", trigger.payload),
                    )
                    deep_rag_status = deep_rag.last_deep_rag_status

                    if deep_rag_status in (
                        DeepRagStatus.QUEUED,
                        DeepRagStatus.IN_PROGRESS,
                    ):
                        raise UiPathPendingTriggerError(
                            ErrorCategory.SYSTEM,
                            f"DeepRag is not finished yet. Current status: {deep_rag_status}",
                        )

                    if deep_rag_status != DeepRagStatus.SUCCESSFUL:
                        raise UiPathFaultedTriggerError(
                            ErrorCategory.USER,
                            f"DeepRag '{deep_rag.name}' did not finish successfully.",
                        )

                    trigger_response = deep_rag.content

                    # if response is an empty dictionary, use Deep Rag state as placeholder value
                    if not trigger_response:
                        trigger_response = {
                            "status": deep_rag_status,
                            PropertyName.INTERNAL.value: TriggerMarker.NO_CONTENT.value,
                        }
                    else:
                        trigger_response = trigger_response.model_dump()

                    return trigger_response

            case UiPathResumeTriggerType.BATCH_RAG:
                if trigger.item_key:
                    destination_path = self._extract_field(
                        "destination_path", trigger.payload
                    )
                    assert destination_path is not None
                    try:
                        await uipath.context_grounding.download_batch_transform_result_async(
                            trigger.item_key,
                            destination_path,
                            validate_status=True,
                            index_name=self._extract_field(
                                "index_name", trigger.payload
                            ),
                        )
                    except BatchTransformNotCompleteException as e:
                        raise UiPathPendingTriggerError(
                            ErrorCategory.SYSTEM,
                            f"{e.message}",
                        ) from e

                    return f"Batch transform completed. Modified file available at {os.path.abspath(destination_path)}"

            case UiPathResumeTriggerType.API:
                if trigger.api_resume and trigger.api_resume.inbox_id:
                    try:
                        return await uipath.jobs.retrieve_api_payload_async(
                            trigger.api_resume.inbox_id
                        )
                    except Exception as e:
                        raise UiPathFaultedTriggerError(
                            ErrorCategory.SYSTEM,
                            f"Failed to get trigger payload"
                            f"Error fetching API trigger payload for inbox {trigger.api_resume.inbox_id}: {str(e)}",
                        ) from e

            case _:
                raise UiPathFaultedTriggerError(
                    ErrorCategory.SYSTEM,
                    f"Unexpected trigger type received"
                    f"Trigger type :{type(trigger.trigger_type)} is invalid",
                )

        raise UiPathFaultedTriggerError(
            ErrorCategory.SYSTEM, "Failed to receive payload from HITL action"
        )


class UiPathResumeTriggerCreator:
    """Creates resume triggers from suspend values.

    Implements UiPathResumeTriggerCreatorProtocol.
    """

    async def create_trigger(self, suspend_value: Any) -> UiPathResumeTrigger:
        """Create a resume trigger from a suspend value.

        This method processes the input value and creates an appropriate resume trigger
        for HITL scenarios. It handles different input types:
        - Tasks: Creates or references UiPath tasks with folder information
        - Jobs: Invokes processes or references existing jobs with folder information
        - API: Creates API triggers with generated inbox IDs

        Args:
            suspend_value: The value that caused the suspension.
                Can be UiPath models (CreateTask, InvokeProcess, etc.),
                strings, or any other value that needs HITL processing.

        Returns:
            UiPathResumeTrigger ready to be persisted

        Raises:
            UiPathRuntimeError: If action/job creation fails, escalation fails, or an
                unknown model type is encountered.
            Exception: If any underlying UiPath service calls fail.
        """
        uipath = UiPath()

        try:
            trigger_type = self._determine_trigger_type(suspend_value)
            trigger_name = self._determine_trigger_name(suspend_value)

            resume_trigger = UiPathResumeTrigger(
                trigger_type=trigger_type,
                trigger_name=trigger_name,
                payload=serialize_object(suspend_value),
            )

            match trigger_type:
                case UiPathResumeTriggerType.TASK:
                    await self._handle_task_trigger(
                        suspend_value, resume_trigger, uipath
                    )

                case UiPathResumeTriggerType.JOB:
                    await self._handle_job_trigger(
                        suspend_value, resume_trigger, uipath
                    )

                case UiPathResumeTriggerType.API:
                    self._handle_api_trigger(suspend_value, resume_trigger)

                case UiPathResumeTriggerType.DEEP_RAG:
                    await self._handle_deep_rag_job_trigger(
                        suspend_value, resume_trigger, uipath
                    )
                case UiPathResumeTriggerType.BATCH_RAG:
                    await self._handle_batch_rag_job_trigger(
                        suspend_value, resume_trigger, uipath
                    )

                case _:
                    raise UiPathFaultedTriggerError(
                        ErrorCategory.SYSTEM,
                        f"Unexpected model received"
                        f"{type(suspend_value)} is not a valid Human-In-The-Loop model",
                    )
        except Exception as e:
            raise UiPathFaultedTriggerError(
                ErrorCategory.SYSTEM,
                "Failed to create HITL action",
                f"{str(e)}",
            ) from e
        return resume_trigger

    def _determine_trigger_type(self, value: Any) -> UiPathResumeTriggerType:
        """Determines the resume trigger type based on the input value.

        Args:
            value: The suspend value to analyze

        Returns:
            The appropriate UiPathResumeTriggerType based on the input value type.
        """
        if isinstance(value, (CreateTask, WaitTask, CreateEscalation, WaitEscalation)):
            return UiPathResumeTriggerType.TASK
        if isinstance(value, (InvokeProcess, WaitJob)):
            return UiPathResumeTriggerType.JOB
        if isinstance(value, (CreateDeepRag, WaitDeepRag)):
            return UiPathResumeTriggerType.DEEP_RAG
        if isinstance(value, (CreateBatchTransform, WaitBatchTransform)):
            return UiPathResumeTriggerType.BATCH_RAG
        # default to API trigger
        return UiPathResumeTriggerType.API

    def _determine_trigger_name(self, value: Any) -> UiPathResumeTriggerName:
        """Determines the resume trigger name based on the input value.

        Args:
            value: The suspend value to analyze

        Returns:
            The appropriate UiPathResumeTriggerName based on the input value type.
        """
        if isinstance(value, (CreateEscalation, WaitEscalation)):
            return UiPathResumeTriggerName.ESCALATION
        if isinstance(value, (CreateTask, WaitTask)):
            return UiPathResumeTriggerName.TASK
        if isinstance(value, (InvokeProcess, WaitJob)):
            return UiPathResumeTriggerName.JOB
        if isinstance(value, (CreateDeepRag, WaitDeepRag)):
            return UiPathResumeTriggerName.DEEP_RAG
        if isinstance(value, (CreateBatchTransform, WaitBatchTransform)):
            return UiPathResumeTriggerName.BATCH_RAG
        # default to API trigger
        return UiPathResumeTriggerName.API

    async def _handle_task_trigger(
        self, value: Any, resume_trigger: UiPathResumeTrigger, uipath: UiPath
    ) -> None:
        """Handle task-type resume triggers.

        Args:
            value: The suspend value (CreateTask or WaitTask)
            resume_trigger: The resume trigger to populate
            uipath: The UiPath client instance
        """
        resume_trigger.folder_path = value.app_folder_path
        resume_trigger.folder_key = value.app_folder_key

        if isinstance(value, (WaitTask, WaitEscalation)):
            resume_trigger.item_key = value.action.key
        elif isinstance(value, (CreateTask, CreateEscalation)):
            action = await uipath.tasks.create_async(
                title=value.title,
                app_name=value.app_name if value.app_name else "",
                app_folder_path=value.app_folder_path if value.app_folder_path else "",
                app_folder_key=value.app_folder_key if value.app_folder_key else "",
                app_key=value.app_key if value.app_key else "",
                assignee=value.assignee if value.assignee else "",
                data=value.data,
            )
            if not action:
                raise Exception("Failed to create action")
            resume_trigger.item_key = action.key

    async def _handle_deep_rag_job_trigger(
        self, value: Any, resume_trigger: UiPathResumeTrigger, uipath: UiPath
    ) -> None:
        """Handle job-type resume triggers.

        Args:
            value: The suspend value (InvokeProcess or WaitJob)
            resume_trigger: The resume trigger to populate
            uipath: The UiPath client instance
        """
        resume_trigger.folder_path = value.index_folder_path
        resume_trigger.folder_key = value.index_folder_key
        if isinstance(value, WaitDeepRag):
            resume_trigger.item_key = value.deep_rag.id
        elif isinstance(value, CreateDeepRag):
            deep_rag = await uipath.context_grounding.start_deep_rag_async(
                name=value.name,
                index_name=value.index_name,
                prompt=value.prompt,
                glob_pattern=value.glob_pattern,
                citation_mode=value.citation_mode,
                folder_path=value.index_folder_path,
                folder_key=value.index_folder_key,
            )
            if not deep_rag:
                raise Exception("Failed to start deep rag")
            resume_trigger.item_key = deep_rag.id

    async def _handle_batch_rag_job_trigger(
        self, value: Any, resume_trigger: UiPathResumeTrigger, uipath: UiPath
    ) -> None:
        """Handle job-type resume triggers.

        Args:
            value: The suspend value (InvokeProcess or WaitJob)
            resume_trigger: The resume trigger to populate
            uipath: The UiPath client instance
        """
        resume_trigger.folder_path = value.index_folder_path
        resume_trigger.folder_key = value.index_folder_key
        if isinstance(value, WaitBatchTransform):
            resume_trigger.item_key = value.batch_transform.id
        elif isinstance(value, CreateBatchTransform):
            batch_transform = await uipath.context_grounding.start_batch_transform_async(
                name=value.name,
                index_name=value.index_name,
                prompt=value.prompt,
                output_columns=value.output_columns,
                storage_bucket_folder_path_prefix=value.storage_bucket_folder_path_prefix,
                enable_web_search_grounding=value.enable_web_search_grounding,
                folder_path=value.index_folder_path,
                folder_key=value.index_folder_key,
            )
            if not batch_transform:
                raise Exception("Failed to start batch transform")
            resume_trigger.item_key = batch_transform.id

    async def _handle_job_trigger(
        self, value: Any, resume_trigger: UiPathResumeTrigger, uipath: UiPath
    ) -> None:
        """Handle job-type resume triggers.

        Args:
            value: The suspend value (InvokeProcess or WaitJob)
            resume_trigger: The resume trigger to populate
            uipath: The UiPath client instance
        """
        resume_trigger.folder_path = value.process_folder_path
        resume_trigger.folder_key = value.process_folder_key

        if isinstance(value, WaitJob):
            resume_trigger.item_key = value.job.key
        elif isinstance(value, InvokeProcess):
            job = await uipath.processes.invoke_async(
                name=value.name,
                input_arguments=value.input_arguments,
                folder_path=value.process_folder_path,
                folder_key=value.process_folder_key,
            )
            if not job:
                raise Exception("Failed to invoke process")
            resume_trigger.item_key = job.key

    def _handle_api_trigger(
        self, value: Any, resume_trigger: UiPathResumeTrigger
    ) -> None:
        """Handle API-type resume triggers.

        Args:
            value: The suspend value
            resume_trigger: The resume trigger to populate
        """
        resume_trigger.api_resume = UiPathApiTrigger(
            inbox_id=str(uuid.uuid4()), request=serialize_object(value)
        )


class UiPathResumeTriggerHandler:
    """Combined handler for creating and reading resume triggers.

    Implements UiPathResumeTriggerProtocol by composing the creator and reader.
    """

    def __init__(self):
        """Initialize the handler with creator and reader instances."""
        self._creator = UiPathResumeTriggerCreator()
        self._reader = UiPathResumeTriggerReader()

    async def create_trigger(self, suspend_value: Any) -> UiPathResumeTrigger:
        """Create a resume trigger from a suspend value.

        Args:
            suspend_value: The value that caused the suspension.

        Returns:
            UiPathResumeTrigger ready to be persisted

        Raises:
            UiPathRuntimeError: If trigger creation fails
        """
        return await self._creator.create_trigger(suspend_value)

    async def read_trigger(self, trigger: UiPathResumeTrigger) -> Any | None:
        """Read a resume trigger and convert it to runtime-compatible input.

        Args:
            trigger: The resume trigger to read

        Returns:
            The data retrieved from UiPath services, or None if no data is available.

        Raises:
            UiPathRuntimeError: If reading fails or job failed
        """
        return await self._reader.read_trigger(trigger)
