import json
import logging
from typing import Any, Optional, cast

from langgraph.types import Command
from uipath import UiPath
from uipath._cli._runtime._contracts import (
    UiPathErrorCategory,
    UiPathResumeTriggerType,
    UiPathRuntimeStatus,
)

from ._context import LangGraphRuntimeContext
from ._escalation import Escalation
from ._exception import LangGraphRuntimeError

logger = logging.getLogger(__name__)


def try_convert_to_json_format(value: str) -> str:
    try:
        return json.loads(value)
    except json.decoder.JSONDecodeError:
        return value


class LangGraphInputProcessor:
    """
    Handles input processing for graph execution, including resume scenarios
    where it needs to fetch data from UiPath.
    """

    def __init__(self, context: LangGraphRuntimeContext):
        """
        Initialize the LangGraphInputProcessor.

        Args:
            context: The runtime context for the graph execution.
        """
        self.context = context
        self.escalation = Escalation(self.context.config_path)
        self.uipath = UiPath()

    async def process(self) -> Any:
        """
        Process the input data, handling resume scenarios by fetching
        necessary data from UiPath if needed.
        """
        logger.debug(f"Resumed: {self.context.resume} Input: {self.context.input_json}")

        if not self.context.resume:
            return self.context.input_json

        if self.context.input_json:
            return Command(resume=self.context.input_json)

        trigger = await self._get_latest_trigger()
        if not trigger:
            return Command(resume=self.context.input_json)

        type, key, folder_path, folder_key, payload = trigger
        logger.debug(f"ResumeTrigger: {type} {key}")
        if type == UiPathResumeTriggerType.ACTION.value and key:
            action = await self.uipath.actions.retrieve_async(
                key, app_folder_key=folder_key, app_folder_path=folder_path
            )
            logger.debug(f"Action: {action}")
            if action.data is None:
                return Command(resume={})
            if self.escalation and self.escalation.enabled:
                extracted_value = self.escalation.extract_response_value(action.data)
                return Command(resume=extracted_value)
            return Command(resume=action.data)
        elif type == UiPathResumeTriggerType.API.value and key:
            payload = await self._get_api_payload(key)
            if payload:
                return Command(resume=payload)
        elif type == UiPathResumeTriggerType.JOB.value and key:
            job = await self.uipath.jobs.retrieve_async(key)
            if (
                job.state
                and not job.state.lower()
                == UiPathRuntimeStatus.SUCCESSFUL.value.lower()
            ):
                error_code = "INVOKED_PROCESS_FAILURE"
                error_title = "Invoked process did not finish successfully."
                error_detail = try_convert_to_json_format(
                    str(job.job_error or job.info)
                )
                raise LangGraphRuntimeError(
                    error_code,
                    error_title,
                    error_detail,
                    UiPathErrorCategory.USER,
                )
            if job.output_arguments:
                return Command(resume=try_convert_to_json_format(job.output_arguments))
        return Command(resume=self.context.input_json)

    async def _get_latest_trigger(self) -> Optional[tuple[str, str, str, str, str]]:
        """Fetch the most recent trigger from the database."""
        if self.context.memory is None:
            return None
        try:
            await self.context.memory.setup()
            async with (
                self.context.memory.lock,
                self.context.memory.conn.cursor() as cur,
            ):
                await cur.execute(f"""
                    SELECT type, key, folder_path, folder_key, payload
                    FROM {self.context.resume_triggers_table}
                    ORDER BY timestamp DESC
                    LIMIT 1
                """)
                result = await cur.fetchone()
                if result is None:
                    return None
                return cast(tuple[str, str, str, str, str], tuple(result))
        except Exception as e:
            raise LangGraphRuntimeError(
                "DB_QUERY_FAILED",
                "Database query failed",
                f"Error querying resume trigger information: {str(e)}",
                UiPathErrorCategory.SYSTEM,
            ) from e

    async def _get_api_payload(self, inbox_id: str) -> Any:
        """
        Fetch payload data for API triggers.

        Args:
            inbox_id: The Id of the inbox to fetch the payload for.

        Returns:
            The value field from the API response payload, or None if an error occurs.
        """
        try:
            response = self.uipath.api_client.request(
                "GET",
                f"/orchestrator_/api/JobTriggers/GetPayload/{inbox_id}",
                include_folder_headers=True,
            )
            data = response.json()
            return data.get("payload")
        except Exception as e:
            raise LangGraphRuntimeError(
                "API_CONNECTION_ERROR",
                "Failed to get trigger payload",
                f"Error fetching API trigger payload for inbox {inbox_id}: {str(e)}",
                UiPathErrorCategory.SYSTEM,
                response.status_code,
            ) from e
