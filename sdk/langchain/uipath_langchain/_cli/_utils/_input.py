from dataclasses import dataclass
from typing import Any, Optional, cast

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command
from uipath_sdk import UiPathSDK

from ._trigger import ResumeTriggerType

uipath = UiPathSDK()


@dataclass
class GraphInput:
    """
    Handles input processing for graph execution, including resume scenarios
    where it needs to fetch data from UiPath.
    """

    checkpointer: AsyncSqliteSaver

    async def get_latest_trigger(self) -> Optional[tuple[str, str]]:
        """Fetch the most recent trigger from the database."""
        await self.checkpointer.setup()
        async with self.checkpointer.lock, self.checkpointer.conn.cursor() as cur:
            await cur.execute("""
                SELECT type, key
                FROM __uipath_resume_triggers
                ORDER BY timestamp DESC
                LIMIT 1
            """)
            result = await cur.fetchone()
            if result is None:
                return None
            return cast(tuple[str, str], tuple(result))

    async def get_api_payload(self, inbox_id: str) -> Any:
        """
        Fetch payload data for API triggers.

        Args:
            inbox_id: The Id of the inbox to fetch the payload for.

        Returns:
            The value field from the API response payload, or None if an error occurs.
        """
        try:
            response = uipath.api_client.request(
                "GET",
                f"/orchestrator_/api/JobTriggers/GetPayload/{inbox_id}",
                include_folder_headers=True,
            )
            data = response.json()
            print(data)
            return data.get("payload")
        except Exception as e:
            print(f"Error fetching API trigger payload: {e}")
            return None

    async def retrieve(self, input_data: Any, resume: bool = False) -> Any:
        """
        Process the input data, handling resume scenarios by fetching
        necessary data from UiPath if needed.
        """
        if not resume:
            return input_data

        if input_data:
            return input_data

        trigger = await self.get_latest_trigger()
        if not trigger:
            return Command(resume=input_data)

        type, key = trigger
        print(f"[ResumeTrigger]: Retrieve DB {type} {key}")
        if type == ResumeTriggerType.ACTION and key:
            action = uipath.actions.retrieve(key)
            return Command(resume=action.data)
        elif type == ResumeTriggerType.API and key:
            payload = await self.get_api_payload(key)
            if payload:
                return Command(resume=payload)

        return Command(resume=input_data)
