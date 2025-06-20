import logging
from typing import Any, Optional, cast

from langgraph.types import Command
from uipath import UiPath
from uipath._cli._runtime._contracts import (
    UiPathApiTrigger,
    UiPathErrorCategory,
    UiPathResumeTrigger,
    UiPathResumeTriggerType,
)
from uipath._cli._runtime._hitl import HitlReader

from ._context import LangGraphRuntimeContext
from ._exception import LangGraphRuntimeError

logger = logging.getLogger(__name__)


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
        self.uipath = UiPath()

    async def process(self) -> Any:
        """
        Process the input data for graph execution, handling both fresh starts and resume scenarios.

        This method determines whether the graph is being executed fresh or resumed from a previous state.
        For fresh executions, it returns the input JSON directly. For resume scenarios, it fetches
        the latest trigger information from the database and constructs a Command object with the
        appropriate resume data.

        The method handles different types of resume triggers:
        - API triggers: Creates an UiPathApiTrigger with inbox_id and request payload
        - Other triggers: Uses the HitlReader to process the resume data

        Returns:
            Any: For fresh executions, returns the input JSON data directly.
                 For resume scenarios, returns a Command object containing the resume data
                 processed through the appropriate trigger handler.

        Raises:
            LangGraphRuntimeError: If there's an error fetching trigger data from the database
                during resume processing.
        """
        logger.debug(f"Resumed: {self.context.resume} Input: {self.context.input_json}")

        if not self.context.resume:
            return self.context.input_json

        if self.context.input_json:
            return Command(resume=self.context.input_json)

        trigger = await self._get_latest_trigger()
        if not trigger:
            return Command(resume=self.context.input_json)

        trigger_type, key, folder_path, folder_key, payload = trigger
        resume_trigger = UiPathResumeTrigger(
            trigger_type=trigger_type,
            item_key=key,
            folder_path=folder_path,
            folder_key=folder_key,
            payload=payload,
        )
        logger.debug(f"ResumeTrigger: {trigger_type} {key}")

        # populate back expected fields for api_triggers
        if resume_trigger.trigger_type == UiPathResumeTriggerType.API:
            resume_trigger.api_resume = UiPathApiTrigger(
                inbox_id=resume_trigger.item_key, request=resume_trigger.payload
            )
        return Command(resume=await HitlReader.read(resume_trigger))

    async def _get_latest_trigger(self) -> Optional[tuple[str, str, str, str, str]]:
        """
        Fetch the most recent resume trigger from the database.

        This private method queries the resume triggers table to retrieve the latest trigger
        information based on timestamp. It handles database connection setup and executes
        a SQL query to fetch trigger data needed for resume operations.

        The method returns trigger information as a tuple containing:
        - type: The type of trigger (e.g., 'API', 'MANUAL', etc.)
        - key: The unique identifier for the trigger/item
        - folder_path: The path to the folder containing the trigger
        - folder_key: The unique identifier for the folder
        - payload: The serialized payload data associated with the trigger

        Returns:
            Optional[tuple[str, str, str, str, str]]: A tuple containing (type, key, folder_path,
                folder_key, payload) for the most recent trigger, or None if no triggers are found
                or if the memory context is not available.

        Raises:
            LangGraphRuntimeError: If there's an error during database connection setup, query
                execution, or result fetching. The original exception is wrapped with context
                about the database operation failure.
        """
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
