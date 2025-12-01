"""Implementation of UiPath resume trigger protocols."""

import json
import uuid
from typing import Any, Dict

from uipath._cli._utils._common import serialize_object
from uipath._utils._bindings import resolve_folder_from_bindings
from uipath.platform import UiPath
from uipath.platform.action_center import Task
from uipath.platform.common import (
    CreateEscalation,
    CreateTask,
    InvokeProcess,
    WaitEscalation,
    WaitJob,
    WaitTask,
)
from uipath.runtime import (
    UiPathApiTrigger,
    UiPathResumeTrigger,
    UiPathResumeTriggerName,
    UiPathResumeTriggerType,
    UiPathRuntimeStatus,
)
from uipath.runtime.errors import (
    UiPathErrorCategory,
    UiPathErrorCode,
    UiPathRuntimeError,
)


def _try_convert_to_json_format(value: str | None) -> str | None:
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
                    action: Task = await uipath.tasks.retrieve_async(
                        trigger.item_key,
                        app_folder_key=trigger.folder_key,
                        app_folder_path=trigger.folder_path,
                    )
                    if trigger.trigger_name == UiPathResumeTriggerName.ESCALATION:
                        return action

                    return action.data

            case UiPathResumeTriggerType.JOB:
                if trigger.item_key:
                    job = await uipath.jobs.retrieve_async(
                        trigger.item_key,
                        folder_key=trigger.folder_key,
                        folder_path=trigger.folder_path,
                    )
                    job_state = (job.state or "").lower()
                    successful_state = UiPathRuntimeStatus.SUCCESSFUL.value.lower()
                    faulted_state = UiPathRuntimeStatus.FAULTED.value.lower()

                    if job_state == successful_state:
                        output_data = await uipath.jobs.extract_output_async(job)
                        return _try_convert_to_json_format(output_data)

                    raise UiPathRuntimeError(
                        UiPathErrorCode.INVOKED_PROCESS_FAILURE,
                        "Invoked process did not finish successfully.",
                        _try_convert_to_json_format(str(job.job_error or job.info))
                        or "Job error unavailable."
                        if job_state == faulted_state
                        else f"Job {job.key} is {job_state}.",
                    )

            case UiPathResumeTriggerType.API:
                if trigger.api_resume and trigger.api_resume.inbox_id:
                    try:
                        return await uipath.jobs.retrieve_api_payload_async(
                            trigger.api_resume.inbox_id
                        )
                    except Exception as e:
                        raise UiPathRuntimeError(
                            UiPathErrorCode.RETRIEVE_RESUME_TRIGGER_ERROR,
                            "Failed to get trigger payload",
                            f"Error fetching API trigger payload for inbox {trigger.api_resume.inbox_id}: {str(e)}",
                            UiPathErrorCategory.SYSTEM,
                        ) from e
            case _:
                raise UiPathRuntimeError(
                    UiPathErrorCode.UNKNOWN_TRIGGER_TYPE,
                    "Unexpected trigger type received",
                    f"Trigger type :{type(trigger.trigger_type)} is invalid",
                    UiPathErrorCategory.USER,
                )

        raise UiPathRuntimeError(
            UiPathErrorCode.RETRIEVE_RESUME_TRIGGER_ERROR,
            "Failed to receive payload from HITL action",
            detail="Failed to receive payload from HITL action",
            category=UiPathErrorCategory.SYSTEM,
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

                case _:
                    raise UiPathRuntimeError(
                        UiPathErrorCode.UNKNOWN_HITL_MODEL,
                        "Unexpected model received",
                        f"{type(suspend_value)} is not a valid Human-In-The-Loop model",
                        UiPathErrorCategory.USER,
                    )
        except UiPathRuntimeError:
            raise
        except Exception as e:
            raise UiPathRuntimeError(
                UiPathErrorCode.CREATE_RESUME_TRIGGER_ERROR,
                "Failed to create HITL action",
                f"{str(e)}",
                UiPathErrorCategory.SYSTEM,
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
            resolved_path, resolved_key = resolve_folder_from_bindings(
                resource_type="app",
                resource_name=value.app_name,
                folder_path=value.app_folder_path,
            )
            if resolved_path:
                resume_trigger.folder_path = resolved_path
            if resolved_key:
                resume_trigger.folder_key = resolved_key

            # Extract additional escalation metadata if present
            additional_params: Dict[str, Any] = {}
            if isinstance(value, CreateEscalation):
                if value.app_version is not None:
                    additional_params["app_version"] = value.app_version
                if value.priority is not None:
                    additional_params["priority"] = value.priority
                if value.labels is not None:
                    additional_params["labels"] = value.labels
                if value.is_actionable_message_enabled is not None:
                    additional_params["is_actionable_message_enabled"] = (
                        value.is_actionable_message_enabled
                    )
                if value.actionable_message_metadata is not None:
                    additional_params["actionable_message_metadata"] = (
                        value.actionable_message_metadata
                    )
                if value.agent_id is not None:
                    additional_params["agent_id"] = value.agent_id
                if value.instance_id is not None:
                    additional_params["instance_id"] = value.instance_id
                if value.job_key is not None:
                    additional_params["job_key"] = value.job_key
                if value.process_key is not None:
                    additional_params["process_key"] = value.process_key
                if value.resource_key is not None:
                    additional_params["resource_key"] = value.resource_key

            action = await uipath.tasks.create_async(
                title=value.title,
                app_name=value.app_name if value.app_name else "",
                app_folder_path=value.app_folder_path if value.app_folder_path else "",
                app_folder_key=value.app_folder_key if value.app_folder_key else "",
                app_key=value.app_key if value.app_key else "",
                assignee=value.assignee if value.assignee else "",
                data=value.data,
                **additional_params,
            )
            if not action:
                raise Exception("Failed to create action")
            resume_trigger.item_key = action.key

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
            resolved_path, resolved_key = resolve_folder_from_bindings(
                resource_type="process",
                resource_name=value.name,
                folder_path=value.process_folder_path,
            )
            if resolved_path:
                resume_trigger.folder_path = resolved_path
            if resolved_key:
                resume_trigger.folder_key = resolved_key

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
