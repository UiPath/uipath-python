import json
import logging
from functools import cached_property
from typing import Any, Dict, Optional, cast

from langgraph.types import Interrupt, StateSnapshot
from uipath._cli._runtime._contracts import (
    UiPathErrorCategory,
    UiPathResumeTrigger,
    UiPathRuntimeResult,
    UiPathRuntimeStatus,
)
from uipath._cli._runtime._hitl import HitlProcessor

from ._context import LangGraphRuntimeContext
from ._exception import LangGraphRuntimeError

logger = logging.getLogger(__name__)


class LangGraphOutputProcessor:
    """
    Contains and manages the complete output information from graph execution.
    Handles serialization, interrupt data, and file output.
    """

    def __init__(self, context: LangGraphRuntimeContext) -> None:
        """
        Initialize the LangGraphOutputProcessor.

        Args:
            context: The runtime context for the graph execution.
        """
        self.context = context
        self._hitl_processor: Optional[HitlProcessor] = None
        self._resume_trigger: Optional[UiPathResumeTrigger] = None

    @classmethod
    async def create(
        cls, context: LangGraphRuntimeContext
    ) -> "LangGraphOutputProcessor":
        """
        Create and initialize a new LangGraphOutputProcessor instance asynchronously.

        Args:
            context: The runtime context for the graph execution.

        Returns:
            LangGraphOutputProcessor: A new initialized instance.
        """
        instance = cls(context)

        # Process interrupt information during initialization
        state = cast(StateSnapshot, context.state)
        if not state or not hasattr(state, "next") or not state.next:
            return instance

        for task in state.tasks:
            if hasattr(task, "interrupts") and task.interrupts:
                for interrupt in task.interrupts:
                    if isinstance(interrupt, Interrupt):
                        instance._hitl_processor = HitlProcessor(interrupt.value)
                        return instance

        return instance

    @property
    def status(self) -> UiPathRuntimeStatus:
        """Determines the execution status based on state."""
        return (
            UiPathRuntimeStatus.SUSPENDED
            if self._hitl_processor
            else UiPathRuntimeStatus.SUCCESSFUL
        )

    @cached_property
    def serialized_output(self) -> Dict[str, Any]:
        """Serializes the graph execution result."""
        try:
            if self.context.output is None:
                return {}

            return self._serialize_object(self.context.output)

        except Exception as e:
            raise LangGraphRuntimeError(
                "OUTPUT_SERIALIZATION_FAILED",
                "Failed to serialize graph output",
                f"Error serializing output data: {str(e)}",
                UiPathErrorCategory.SYSTEM,
            ) from e

    def _serialize_object(self, obj):
        """Recursively serializes an object and all its nested components."""
        # Handle Pydantic models
        if hasattr(obj, "dict"):
            return self._serialize_object(obj.dict())
        elif hasattr(obj, "model_dump"):
            return self._serialize_object(obj.model_dump(by_alias=True))
        elif hasattr(obj, "to_dict"):
            return self._serialize_object(obj.to_dict())
        # Handle dictionaries
        elif isinstance(obj, dict):
            return {k: self._serialize_object(v) for k, v in obj.items()}
        # Handle lists
        elif isinstance(obj, list):
            return [self._serialize_object(item) for item in obj]
        # Handle other iterable objects (convert to dict first)
        elif hasattr(obj, "__iter__") and not isinstance(obj, (str, bytes)):
            try:
                return self._serialize_object(dict(obj))
            except (TypeError, ValueError):
                return obj
        # Return primitive types as is
        else:
            return obj

    async def process(self) -> UiPathRuntimeResult:
        """
        Process the output and prepare the final execution result.

        Returns:
            UiPathRuntimeResult: The processed execution result.

        Raises:
            LangGraphRuntimeError: If processing fails.
        """
        try:
            await self._save_resume_trigger()

            return UiPathRuntimeResult(
                output=self.serialized_output,
                status=self.status,
                resume=self._resume_trigger if self._resume_trigger else None,
            )

        except LangGraphRuntimeError:
            raise
        except Exception as e:
            raise LangGraphRuntimeError(
                "OUTPUT_PROCESSING_FAILED",
                "Failed to process execution output",
                f"Unexpected error during output processing: {str(e)}",
                UiPathErrorCategory.SYSTEM,
            ) from e

    async def _save_resume_trigger(self) -> None:
        """
        Stores the resume trigger in the SQLite database if available.

        Raises:
            LangGraphRuntimeError: If database operations fail.
        """
        if not self._hitl_processor or not self.context.memory:
            return

        try:
            await self.context.memory.setup()
            async with (
                self.context.memory.lock,
                self.context.memory.conn.cursor() as cur,
            ):
                try:
                    await cur.execute(f"""
                        CREATE TABLE IF NOT EXISTS {self.context.resume_triggers_table} (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            type TEXT NOT NULL,
                            key TEXT,
                            folder_key TEXT,
                            folder_path TEXT,
                            payload TEXT,
                            timestamp DATETIME DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now', 'utc'))
                        )
                    """)
                except Exception as e:
                    raise LangGraphRuntimeError(
                        "DB_TABLE_CREATION_FAILED",
                        "Failed to create resume triggers table",
                        f"Database error while creating table: {str(e)}",
                        UiPathErrorCategory.SYSTEM,
                    ) from e

                try:
                    self._resume_trigger = (
                        await self._hitl_processor.create_resume_trigger()
                    )
                except Exception as e:
                    raise LangGraphRuntimeError(
                        "HITL_EVENT_CREATION_FAILED",
                        "Failed to process HITL request",
                        f"Error while trying to process HITL request: {str(e)}",
                        UiPathErrorCategory.SYSTEM,
                    ) from e
                    # if API trigger, override item_key and payload
                if self._resume_trigger:
                    if self._resume_trigger.api_resume:
                        trigger_key = self._resume_trigger.api_resume.inbox_id
                    else:
                        trigger_key = self._resume_trigger.item_key
                    try:
                        logger.debug(
                            f"ResumeTrigger: {self._resume_trigger.trigger_type} {self._resume_trigger.item_key}"
                        )
                        if isinstance(self._resume_trigger.payload, dict):
                            payload = json.dumps(self._resume_trigger.payload)
                        else:
                            payload = str(self._resume_trigger.payload)
                        await cur.execute(
                            f"INSERT INTO {self.context.resume_triggers_table} (type, key, payload, folder_path, folder_key) VALUES (?, ?, ?, ?, ?)",
                            (
                                self._resume_trigger.trigger_type.value,
                                trigger_key,
                                payload,
                                self._resume_trigger.folder_path,
                                self._resume_trigger.folder_key,
                            ),
                        )
                        await self.context.memory.conn.commit()
                    except Exception as e:
                        raise LangGraphRuntimeError(
                            "DB_INSERT_FAILED",
                            "Failed to save resume trigger",
                            f"Database error while saving resume trigger: {str(e)}",
                            UiPathErrorCategory.SYSTEM,
                        ) from e
        except LangGraphRuntimeError:
            raise
        except Exception as e:
            raise LangGraphRuntimeError(
                "RESUME_TRIGGER_SAVE_FAILED",
                "Failed to save resume trigger",
                f"Unexpected error while saving resume trigger: {str(e)}",
                UiPathErrorCategory.SYSTEM,
            ) from e
