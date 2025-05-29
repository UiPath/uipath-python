import json
import uuid
from dataclasses import dataclass
from functools import cached_property
from typing import Any, Optional

from uipath import UiPath
from uipath.models import CreateAction, InvokeProcess, WaitAction, WaitJob

from .._runtime._contracts import (
    UiPathApiTrigger,
    UiPathErrorCategory,
    UiPathResumeTrigger,
    UiPathResumeTriggerType,
    UiPathRuntimeError,
    UiPathRuntimeStatus,
)


def _try_convert_to_json_format(value: str) -> str:
    try:
        return json.loads(value)
    except json.decoder.JSONDecodeError:
        return value


async def _get_api_payload(inbox_id: str) -> Any:
    """Fetch payload data for API triggers.

    Args:
        inbox_id: The Id of the inbox to fetch the payload for.

    Returns:
        The value field from the API response payload, or None if an error occurs.
    """
    response = None
    try:
        uipath = UiPath()
        response = uipath.api_client.request(
            "GET",
            f"/orchestrator_/api/JobTriggers/GetPayload/{inbox_id}",
            include_folder_headers=True,
        )
        data = response.json()
        return data.get("payload")
    except Exception as e:
        raise UiPathRuntimeError(
            "API_CONNECTION_ERROR",
            "Failed to get trigger payload",
            f"Error fetching API trigger payload for inbox {inbox_id}: {str(e)}",
            UiPathErrorCategory.SYSTEM,
            response.status_code if response else None,
        ) from e


class HitlReader:
    @classmethod
    async def read(cls, resume_trigger: UiPathResumeTrigger) -> Optional[str]:
        uipath = UiPath()
        match resume_trigger.trigger_type:
            case UiPathResumeTriggerType.ACTION:
                if resume_trigger.item_key:
                    action = await uipath.actions.retrieve_async(
                        resume_trigger.item_key,
                        app_folder_key=resume_trigger.folder_key,
                        app_folder_path=resume_trigger.folder_path,
                    )
                    return action.data

            case UiPathResumeTriggerType.JOB:
                if resume_trigger.item_key:
                    job = await uipath.jobs.retrieve_async(
                        resume_trigger.item_key,
                        folder_key=resume_trigger.folder_key,
                        folder_path=resume_trigger.folder_path,
                    )
                    if (
                        job.state
                        and not job.state.lower()
                        == UiPathRuntimeStatus.SUCCESSFUL.value.lower()
                    ):
                        raise UiPathRuntimeError(
                            "INVOKED_PROCESS_FAILURE",
                            "Invoked process did not finish successfully.",
                            _try_convert_to_json_format(str(job.job_error or job.info)),
                        )
                    return job.output_arguments

            case UiPathResumeTriggerType.API:
                if resume_trigger.api_resume and resume_trigger.api_resume.inbox_id:
                    return await _get_api_payload(resume_trigger.api_resume.inbox_id)

            case _:
                raise UiPathRuntimeError(
                    "UNKNOWN_TRIGGER_TYPE",
                    "Unexpected trigger type received",
                    f"Trigger type :{type(resume_trigger.trigger_type)} is invalid",
                    UiPathErrorCategory.USER,
                )

        raise UiPathRuntimeError(
            "HITL_FEEDBACK_FAILURE",
            "Failed to receive payload from HITL action",
            detail="Failed to receive payload from HITL action",
            category=UiPathErrorCategory.SYSTEM,
        )


@dataclass
class HitlProcessor:
    """Processes events in a Human-(Robot/Agent)-In-The-Loop scenario."""

    value: Any

    @cached_property
    def type(self) -> UiPathResumeTriggerType:
        """Returns the type of the interrupt value."""
        if isinstance(self.value, CreateAction) or isinstance(self.value, WaitAction):
            return UiPathResumeTriggerType.ACTION
        if isinstance(self.value, InvokeProcess) or isinstance(self.value, WaitJob):
            return UiPathResumeTriggerType.JOB
        # default to API trigger
        return UiPathResumeTriggerType.API

    async def create_resume_trigger(self) -> Optional[UiPathResumeTrigger]:
        """Returns the resume trigger."""
        uipath = UiPath()
        try:
            hitl_input = self.value
            resume_trigger = UiPathResumeTrigger(
                trigger_type=self.type, payload=hitl_input.model_dump_json()
            )
            match self.type:
                case UiPathResumeTriggerType.ACTION:
                    resume_trigger.folder_path = hitl_input.app_folder_path
                    resume_trigger.folder_key = hitl_input.app_folder_key
                    if isinstance(hitl_input, WaitAction):
                        resume_trigger.item_key = hitl_input.action.key
                    elif isinstance(hitl_input, CreateAction):
                        action = await uipath.actions.create_async(
                            title=hitl_input.title,
                            app_name=hitl_input.app_name if hitl_input.app_name else "",
                            app_folder_path=hitl_input.app_folder_path
                            if hitl_input.app_folder_path
                            else "",
                            app_folder_key=hitl_input.app_folder_key
                            if hitl_input.app_folder_key
                            else "",
                            app_key=hitl_input.app_key if hitl_input.app_key else "",
                            app_version=hitl_input.app_version
                            if hitl_input.app_version
                            else 1,
                            assignee=hitl_input.assignee if hitl_input.assignee else "",
                            data=hitl_input.data,
                        )
                        if action:
                            resume_trigger.item_key = action.key

                case UiPathResumeTriggerType.JOB:
                    resume_trigger.folder_path = hitl_input.process_folder_path
                    resume_trigger.folder_key = hitl_input.process_folder_key
                    if isinstance(hitl_input, WaitJob):
                        resume_trigger.item_key = hitl_input.job.key
                    elif isinstance(hitl_input, InvokeProcess):
                        job = await uipath.processes.invoke_async(
                            name=hitl_input.name,
                            input_arguments=hitl_input.input_arguments,
                            folder_path=hitl_input.process_folder_path,
                            folder_key=hitl_input.process_folder_key,
                        )
                        if job:
                            resume_trigger.item_key = job.key

                case UiPathResumeTriggerType.API:
                    resume_trigger.api_resume = UiPathApiTrigger(
                        inbox_id=str(uuid.uuid4()), request=hitl_input.prefix
                    )
                case _:
                    raise UiPathRuntimeError(
                        "UNKNOWN_HITL_MODEL",
                        "Unexpected model received",
                        f"{type(hitl_input)} is not a valid Human(Robot/Agent)-In-The-Loop model",
                        UiPathErrorCategory.USER,
                    )
        except Exception as e:
            raise UiPathRuntimeError(
                "HITL_ACTION_CREATION_FAILED",
                "Failed to create HITL action",
                f"{str(e)}",
                UiPathErrorCategory.SYSTEM,
            ) from e

        return resume_trigger
